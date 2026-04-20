from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesRegressor, HistGradientBoostingRegressor
from sklearn.linear_model import ElasticNet, Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from .data_entity import build_entity_ml_dataset, list_available_entities
from .data_quality import assess_ml_dataset_quality, resolve_test_years
from .train import temporal_split
from .data import FAMILIES

DEFAULT_OUTPUT_DIR = Path("data/processed/ml/entity")
PREDICTIONS_FILENAME = "predictions.csv"
METRICS_FILENAME = "metrics.json"


def _make_model(model_name: str):
    if model_name == "ridge":
        return Pipeline([("scaler", StandardScaler()), ("regressor", Ridge(alpha=10.0, random_state=42))])
    if model_name == "enet":
        return Pipeline(
            [
                ("scaler", StandardScaler()),
                ("regressor", ElasticNet(alpha=0.01, l1_ratio=0.6, random_state=42, max_iter=25000)),
            ]
        )
    if model_name == "et":
        return Pipeline(
            [
                ("scaler", StandardScaler()),
                (
                    "regressor",
                    ExtraTreesRegressor(
                        n_estimators=350,
                        max_depth=10,
                        min_samples_leaf=1,
                        random_state=42,
                        n_jobs=-1,
                    ),
                ),
            ]
        )
    if model_name == "hgb":
        return HistGradientBoostingRegressor(
            max_iter=350,
            learning_rate=0.04,
            max_depth=6,
            random_state=42,
        )
    raise RuntimeError(f"Unsupported model: {model_name}")


def _dedupe(seq: list[str]) -> list[str]:
    out = []
    seen = set()
    for item in seq:
        key = str(item).strip()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(key)
    return out


def _base_feature_pool(df: pd.DataFrame) -> list[str]:
    preferred = [
        "target_share_prev",
        "target_share_prev2",
        "target_share_momentum",
        "lineage_share_prev",
        "lineage_share_prev2",
        "lineage_share_momentum",
        "share_winner_prev",
        "share_winner_prev2",
        "share_winner_momentum",
        "election_number",
        "population_density",
        "population_log",
        "latitude",
        "longitude",
        "abstention_rate_prev",
        "valid_ballot_rate_prev",
        "invalid_ballot_rate_prev",
        "registered",
        "votes_cast",
        "votes_valid",
        "votes",
        "extreme_gauche_prev",
        "gauche_prev",
        "centre_prev",
        "droite_prev",
        "extreme_droite_prev",
        "droite_nat_prev",
        "left_bloc_strength",
        "right_bloc_strength",
        "center_competition",
        "left_pressure",
        "right_pressure",
        "droite_gap_vs_extreme",
        "gauche_gap_vs_extreme",
        "municipal_turnout_rate_latest",
        "municipal_valid_ballot_rate_latest",
        "municipal_winner_share_latest",
        "municipal_num_candidates_latest",
        "municipal_hhi_latest",
    ]
    preferred = [col for col in preferred if col in df.columns]

    thematic = [
        col
        for col in df.columns
        if str(col).startswith(("eco_", "edu_", "demo_", "env_", "com_"))
    ]
    thematic = [col for col in thematic if col in df.columns]

    return _dedupe(preferred + thematic)


def _feature_variants(df: pd.DataFrame) -> list[tuple[str, list[str]]]:
    base = _base_feature_pool(df)
    variants: list[tuple[str, list[str]]] = []
    if base:
        variants.append(("base", base))

    with_nowcast = _dedupe(base + [c for c in ["registered", "votes_cast", "votes_valid", "votes"] if c in df.columns])
    if with_nowcast and with_nowcast != base:
        variants.append(("base_plus_nowcast", with_nowcast))

    reserved = {
        "year",
        "geo_code",
        "dept_code",
        "scope",
        "target",
        "target_share",
        "lineage_share",
        "share_winner",
        "entity_mode",
        "entity_id",
        "entity_label",
        "lineage_id",
        "candidate_id",
        "candidate_label",
        "party_lineage",
    }
    reserved.update(FAMILIES)
    numeric_all = []
    for col in df.columns:
        if col in reserved:
            continue
        if pd.api.types.is_numeric_dtype(df[col]):
            numeric_all.append(col)
    numeric_all = _dedupe(numeric_all)
    if numeric_all and numeric_all != base and numeric_all != with_nowcast:
        variants.append(("full_numeric", numeric_all))
    return variants


def _prepare_xy(df: pd.DataFrame, feature_cols: list[str]) -> tuple[pd.DataFrame, np.ndarray, pd.DataFrame]:
    data = df.copy()
    data["target"] = pd.to_numeric(data.get("target"), errors="coerce")
    data = data.dropna(subset=["target"]).copy()
    features = [col for col in feature_cols if col in data.columns]
    if not features:
        raise RuntimeError("No features available after filtering.")
    x = data[features].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    y = data["target"].astype(float).values
    return x, y, data


def train_entity(
    entity: str,
    entity_mode: str = "candidate",
    scope: str = "commune",
    use_db: bool = True,
    test_years: list[int] | None = None,
    min_train_year: int | None = None,
    output_dir: Path | None = None,
    include_absent_years: bool = False,
    model_candidates: list[str] | None = None,
    max_seconds: int = 180,
) -> dict:
    output_dir = Path(output_dir or DEFAULT_OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)

    df, meta = build_entity_ml_dataset(
        entity=entity,
        entity_mode=entity_mode,
        use_db=use_db,
        include_lags=True,
        scope=scope,
        include_absent_years=include_absent_years,
    )
    resolved_test_years = resolve_test_years(df, test_years)

    quality_cols = _base_feature_pool(df)
    quality_report = assess_ml_dataset_quality(
        df=df,
        target="target",
        scope=scope,
        feature_columns=quality_cols,
        test_years=resolved_test_years,
    )
    quality_report_path = output_dir / "data_quality_report.json"
    with open(quality_report_path, "w", encoding="utf-8") as f:
        json.dump(quality_report, f, indent=2, ensure_ascii=False)
    if quality_report.get("status") != "pass":
        raise RuntimeError(
            "Echec des controles qualite des donnees (entity). "
            f"Rapport={quality_report_path}"
        )

    train_df, test_df = temporal_split(
        df,
        test_years=resolved_test_years,
        exclude_first_election_from_train=False,
    )
    if min_train_year is not None:
        train_df = train_df[train_df["year"] >= int(min_train_year)].copy()
    if train_df.empty or test_df.empty:
        raise RuntimeError(
            "Jeu train/test vide. "
            f"train_rows={len(train_df)} test_rows={len(test_df)} test_years={resolved_test_years}"
        )

    models = _dedupe(model_candidates or ["ridge", "enet", "hgb", "et"])
    variants = _feature_variants(df)
    if not variants:
        raise RuntimeError("Aucune variante de features disponible.")

    best = None
    best_pred = None
    best_y = None
    best_test_clean = None
    tested = 0
    start = time.monotonic()
    timeout_hit = False

    for model_name in models:
        for variant_name, features in variants:
            if max_seconds > 0 and (time.monotonic() - start) >= float(max_seconds):
                timeout_hit = True
                break

            try:
                x_train, y_train, _ = _prepare_xy(train_df, features)
                x_test, y_test, test_clean = _prepare_xy(test_df, features)
            except RuntimeError:
                continue
            if x_train.empty or x_test.empty:
                continue

            model = _make_model(model_name)
            model.fit(x_train, y_train)
            pred = np.clip(model.predict(x_test), 0.0, 1.0)

            row = {
                "model": model_name,
                "feature_variant": variant_name,
                "features": features,
                "r2": float(r2_score(y_test, pred)),
                "mae": float(mean_absolute_error(y_test, pred)),
                "rmse": float(np.sqrt(mean_squared_error(y_test, pred))),
            }
            tested += 1
            if best is None:
                best = row
                best_pred = pred
                best_y = y_test
                best_test_clean = test_clean
            else:
                best_key = (float(best["r2"]), -float(best["mae"]), -float(best["rmse"]))
                row_key = (float(row["r2"]), -float(row["mae"]), -float(row["rmse"]))
                if row_key > best_key:
                    best = row
                    best_pred = pred
                    best_y = y_test
                    best_test_clean = test_clean
        if timeout_hit:
            break

    if best is None or best_pred is None or best_y is None or best_test_clean is None:
        raise RuntimeError("Aucune configuration valide pour cet entity.")

    # Baseline from lagged target share.
    selected_mode = "model"
    selected_pred = best_pred.astype(float)
    baseline_metrics = {}
    baseline_col = "target_share_prev"
    if baseline_col in best_test_clean.columns:
        baseline_pred = (
            pd.to_numeric(best_test_clean[baseline_col], errors="coerce")
            .fillna(0.0)
            .astype(float)
            .clip(0.0, 1.0)
            .values
        )
        if len(baseline_pred) == len(best_y):
            baseline_r2 = float(r2_score(best_y, baseline_pred))
            baseline_metrics = {
                "baseline_lag_column": baseline_col,
                "baseline_mae": float(mean_absolute_error(best_y, baseline_pred)),
                "baseline_rmse": float(np.sqrt(mean_squared_error(best_y, baseline_pred))),
                "baseline_r2": baseline_r2,
            }
            if baseline_r2 >= float(best["r2"]):
                selected_mode = "baseline_fallback"
                selected_pred = baseline_pred

    final_mae = float(mean_absolute_error(best_y, selected_pred))
    final_rmse = float(np.sqrt(mean_squared_error(best_y, selected_pred)))
    final_r2 = float(r2_score(best_y, selected_pred))

    pred_df = best_test_clean[["year", "geo_code", "dept_code"]].copy()
    pred_df["actual"] = best_y.astype(float)
    pred_df["pred_model_only"] = best_pred.astype(float)
    pred_df["pred_selected"] = selected_pred.astype(float)
    pred_df["selected_prediction_mode"] = selected_mode
    pred_df["entity_mode"] = entity_mode
    pred_df["entity_id"] = meta["entity_id"]
    pred_df["entity_label"] = meta["entity_label"]
    pred_df["abs_error_model_only"] = np.abs(pred_df["actual"] - pred_df["pred_model_only"])
    pred_df["abs_error_selected"] = np.abs(pred_df["actual"] - pred_df["pred_selected"])
    pred_path = output_dir / PREDICTIONS_FILENAME
    pred_df.to_csv(pred_path, index=False)

    metrics = {
        "entity_mode": entity_mode,
        "entity_id": meta["entity_id"],
        "entity_label": meta["entity_label"],
        "lineage_id": meta["lineage_id"],
        "scope": scope,
        "test_years": resolved_test_years,
        "min_train_year": min_train_year,
        "include_absent_years": bool(include_absent_years),
        "selected_prediction_mode": selected_mode,
        "model_type": best["model"],
        "feature_variant": best["feature_variant"],
        "features": best["features"],
        "mae": final_mae,
        "rmse": final_rmse,
        "r2": final_r2,
        "model_only_mae": float(best["mae"]),
        "model_only_rmse": float(best["rmse"]),
        "model_only_r2": float(best["r2"]),
        "tested_candidates": int(tested),
        "search_timeout_seconds": int(max_seconds),
        "search_timeout_hit": bool(timeout_hit),
        "data_quality_status": quality_report.get("status"),
        "data_quality_critical_count": int(len(quality_report.get("critical_issues", []))),
        "data_quality_warning_count": int(len(quality_report.get("warning_issues", []))),
        "data_quality_report_file": str(quality_report_path),
        "predictions_file": str(pred_path),
        "years_present": meta.get("years_present", []),
    }
    if baseline_metrics:
        metrics.update(baseline_metrics)

    metrics_path = output_dir / METRICS_FILENAME
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2, ensure_ascii=False)
    return metrics


def _parse_csv_ints(raw: str) -> list[int] | None:
    text = str(raw or "").strip().lower()
    if text in {"", "latest"}:
        return None
    return [int(x.strip()) for x in text.split(",") if x.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description="Entrainement ML par entite (candidat ou parti-lineage).")
    parser.add_argument("--entity-mode", choices=["candidate", "party"], default="candidate")
    parser.add_argument(
        "--entity",
        type=str,
        default="",
        help="Nom/identifiant de l'entite (ex: 'LE PEN', 'MACRON', 'RN').",
    )
    parser.add_argument("--list-entities", action="store_true", help="Lister les entites disponibles puis quitter.")
    parser.add_argument("--scope", choices=["departement", "commune"], default="commune")
    parser.add_argument("--no-db", action="store_true")
    parser.add_argument("--test-years", type=str, default="latest")
    parser.add_argument("--min-train-year", type=int, default=None)
    parser.add_argument("--include-absent-years", action="store_true", default=False)
    parser.add_argument("--model-candidates", type=str, default="ridge,enet,hgb,et")
    parser.add_argument("--max-seconds", type=int, default=180)
    parser.add_argument("--output-dir", type=str, default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args()

    use_db = not args.no_db
    if args.list_entities:
        summary = list_available_entities(
            entity_mode=args.entity_mode,
            use_db=use_db,
            scope=args.scope,
        )
        if summary.empty:
            print("[info] Aucune entite disponible.")
            return 0
        print(summary.to_string(index=False))
        return 0

    entity = str(args.entity or "").strip()
    if not entity:
        raise RuntimeError("--entity est requis (ou utiliser --list-entities).")

    model_candidates = _dedupe([x.strip() for x in str(args.model_candidates).split(",") if x.strip()])
    metrics = train_entity(
        entity=entity,
        entity_mode=args.entity_mode,
        scope=args.scope,
        use_db=use_db,
        test_years=_parse_csv_ints(args.test_years),
        min_train_year=args.min_train_year,
        output_dir=Path(args.output_dir),
        include_absent_years=bool(args.include_absent_years),
        model_candidates=model_candidates,
        max_seconds=int(args.max_seconds),
    )

    print(
        f"[done] entity={metrics['entity_id']} mode={metrics['entity_mode']} "
        f"model={metrics['model_type']} selected_mode={metrics['selected_prediction_mode']} "
        f"R2={metrics['r2']:.4f} MAE={metrics['mae']:.4f} quality={metrics['data_quality_status']}"
    )
    print(f"[done] metrics={Path(args.output_dir) / METRICS_FILENAME}")
    print(f"[done] predictions={Path(args.output_dir) / PREDICTIONS_FILENAME}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
