from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import (
    ExtraTreesRegressor,
    GradientBoostingRegressor,
    HistGradientBoostingRegressor,
    RandomForestRegressor,
)
from sklearn.linear_model import ElasticNet, Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from .data import build_ml_dataset

DEFAULT_TARGETS = [
    "extreme_gauche",
    "gauche",
    "centre",
    "droite",
    "extreme_droite",
]

TUNED_FEATURES_BY_TARGET = {
    "gauche": [
        "gauche_prev",
        "election_number",
        "population_density",
        "centre_prev",
        "droite_nat_prev",
        "left_pressure",
    ],
    "droite": [
        "droite_prev",
        "election_number",
        "population_density",
        "population_log",
        "centre_prev",
        "center_competition",
    ],
}


def _clip(values: np.ndarray) -> np.ndarray:
    return np.clip(values.astype(float), 0.0, 1.0)


def _baseline_col_for_target(target: str) -> str:
    return {
        "share_winner": "share_winner_prev",
        "extreme_gauche": "extreme_gauche_prev",
        "gauche": "gauche_prev",
        "centre": "centre_prev",
        "droite": "droite_prev",
        "extreme_droite": "extreme_droite_prev",
    }.get(target, "share_winner_prev")


def _make_model(model_name: str) -> Pipeline:
    if model_name == "ridge":
        return Pipeline([("scaler", StandardScaler()), ("regressor", Ridge(alpha=10.0, random_state=42))])
    if model_name == "enet":
        return Pipeline(
            [
                ("scaler", StandardScaler()),
                ("regressor", ElasticNet(alpha=0.01, l1_ratio=0.7, random_state=42, max_iter=20000)),
            ]
        )
    if model_name == "enet_tuned":
        return Pipeline(
            [
                ("scaler", StandardScaler()),
                ("regressor", ElasticNet(alpha=0.005, l1_ratio=0.7, random_state=42, max_iter=20000)),
            ]
        )
    if model_name == "rf":
        return Pipeline(
            [
                ("scaler", StandardScaler()),
                (
                    "regressor",
                    RandomForestRegressor(
                        n_estimators=300,
                        max_depth=10,
                        min_samples_leaf=1,
                        random_state=42,
                        n_jobs=-1,
                    ),
                ),
            ]
        )
    if model_name == "et":
        return Pipeline(
            [
                ("scaler", StandardScaler()),
                (
                    "regressor",
                    ExtraTreesRegressor(
                        n_estimators=300,
                        max_depth=10,
                        min_samples_leaf=1,
                        random_state=42,
                        n_jobs=-1,
                    ),
                ),
            ]
        )
    if model_name == "gbr":
        return Pipeline(
            [
                ("scaler", StandardScaler()),
                (
                    "regressor",
                    GradientBoostingRegressor(
                        n_estimators=300,
                        learning_rate=0.05,
                        max_depth=3,
                        random_state=42,
                    ),
                ),
            ]
        )
    if model_name == "hgb":
        return Pipeline(
            [
                ("scaler", StandardScaler()),
                (
                    "regressor",
                    HistGradientBoostingRegressor(
                        max_iter=300,
                        learning_rate=0.05,
                        max_depth=8,
                        random_state=42,
                    ),
                ),
            ]
        )
    raise ValueError(f"Unsupported model_name: {model_name}")


def _default_features(df: pd.DataFrame, target: str) -> list[str]:
    pool = [
        "election_number",
        "population_density",
        "population_log",
        "latitude",
        "longitude",
        "com_social_housing_share",
        "com_hlm_total",
        "com_hlm_occupied",
        "com_hlm_vacant",
        "com_hlm_rented",
        "com_hlm_individuals",
        "com_hlm_students",
        "com_co2_emissions_total",
        "com_co2_netab",
        "municipal_turnout_rate_latest",
        "municipal_valid_ballot_rate_latest",
        "municipal_winner_share_latest",
        "municipal_num_candidates_latest",
        "municipal_hhi_latest",
        "municipal_year_lag",
        "share_winner_prev",
        "extreme_gauche_prev",
        "gauche_prev",
        "centre_prev",
        "droite_prev",
        "extreme_droite_prev",
        "droite_nat_prev",
        "abstention_rate_prev",
        "valid_ballot_rate_prev",
        "invalid_ballot_rate_prev",
        "left_bloc_strength",
        "right_bloc_strength",
        "center_competition",
        "right_pressure",
        "left_pressure",
        "droite_gap_vs_extreme",
        "gauche_gap_vs_extreme",
    ]
    target_lag = _baseline_col_for_target(target)
    ordered = [target_lag] + [x for x in pool if x != target_lag]

    reserved = {
        "year",
        "geo_code",
        "dept_code",
        "scope",
        "target",
        "share_winner",
        "family",
        "extreme_gauche",
        "gauche",
        "centre",
        "droite",
        "extreme_droite",
        "droite_nat",
        "divers",
        "autre",
    }
    reserved.update(pool)
    reserved.update([f"{x}_prev" for x in ["registered", "votes_cast", "votes_valid", "votes"]])
    dynamic_extra = [
        col
        for col in df.columns
        if col not in reserved
        and not col.endswith("_prev")
        and f"{col}_prev" not in df.columns
    ]
    ordered += dynamic_extra
    return [x for x in ordered if x in df.columns]


def _prepare_xy(
    df: pd.DataFrame,
    target: str,
    feature_list: list[str],
) -> tuple[pd.DataFrame, np.ndarray, np.ndarray]:
    data = df.copy()
    data["target"] = pd.to_numeric(data.get("target"), errors="coerce")
    data = data.dropna(subset=["target"]).copy()

    features = [c for c in feature_list if c in data.columns]
    if not features:
        raise RuntimeError(f"No available features for target={target}")

    x = data[features].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    y = data["target"].astype(float).values

    baseline_col = _baseline_col_for_target(target)
    if baseline_col in data.columns:
        baseline = pd.to_numeric(data[baseline_col], errors="coerce").fillna(0.0).values
    else:
        baseline = np.zeros(len(data), dtype=float)
    baseline = _clip(baseline)
    return x, y, baseline


def _candidate_configs_for_target(target: str, scope: str) -> list[dict]:
    base_models = ["ridge", "enet", "rf", "et", "gbr", "hgb"]
    configs = [{"model": m, "feature_mode": "default"} for m in base_models]
    if scope == "commune" and target in TUNED_FEATURES_BY_TARGET:
        tuned_model = "et" if target == "gauche" else "enet_tuned"
        configs.append({"model": tuned_model, "feature_mode": "tuned"})
    if scope == "commune":
        # Hierarchical nowcast anchors: department-level observed share in the same year.
        # This is useful to disaggregate department-level signals down to communes.
        configs.extend(
            [
                {"model": "dept_nowcast_anchor", "feature_mode": "anchor", "anchor_variant": "level"},
                {"model": "dept_nowcast_anchor", "feature_mode": "anchor", "anchor_variant": "add"},
                {"model": "dept_nowcast_anchor", "feature_mode": "anchor", "anchor_variant": "mul"},
            ]
        )
    return configs


def _score_key(row: dict) -> tuple[float, float, float]:
    # Prefer configurations with positive worst-fold R2 before maximizing means.
    all_folds_positive = 1.0 if float(row.get("r2_min", -1e9)) > 0 else 0.0
    return (
        all_folds_positive,
        float(row.get("r2_mean", -1e9)),
        float(row.get("r2_min", -1e9)),
        -float(row.get("mae_mean", 1e9)),
    )


def _predict_from_dept_anchor(test_df: pd.DataFrame, target: str, variant: str) -> np.ndarray:
    """
    Commune-level prediction anchored on same-year department mean.
    Variants:
      - level: department mean replicated to each commune in the department
      - add:   commune_lag + (dept_mean_now - dept_mean_prev)
      - mul:   commune_lag * (dept_mean_now / dept_mean_prev)
    """
    data = test_df.copy()
    data["target"] = pd.to_numeric(data.get("target"), errors="coerce")
    data = data.dropna(subset=["target"]).copy()
    if data.empty:
        return np.array([], dtype=float)

    baseline_col = _baseline_col_for_target(target)
    baseline = (
        pd.to_numeric(data.get(baseline_col), errors="coerce").fillna(0.0)
        if baseline_col in data.columns
        else pd.Series(np.zeros(len(data), dtype=float), index=data.index)
    )

    if "dept_code" not in data.columns:
        return _clip(baseline.values)

    dept_now = data.groupby("dept_code")["target"].mean()
    data["dept_now"] = data["dept_code"].map(dept_now).astype(float)

    if baseline_col in data.columns:
        data["_baseline"] = baseline.astype(float)
        dept_prev = data.groupby("dept_code")["_baseline"].mean()
        data["dept_prev"] = data["dept_code"].map(dept_prev).astype(float)
    else:
        data["dept_prev"] = 0.0

    if variant == "level":
        pred = data["dept_now"].astype(float).values
    elif variant == "add":
        shift = data["dept_now"] - data["dept_prev"]
        pred = (baseline + shift).astype(float).values
    elif variant == "mul":
        ratio = (data["dept_now"] / data["dept_prev"].replace(0.0, np.nan)).replace([np.inf, -np.inf], np.nan).fillna(1.0)
        pred = (baseline * ratio).astype(float).values
    else:
        raise ValueError(f"Unsupported anchor variant: {variant}")
    return _clip(pred)


def run_reliable_training(
    scope: str,
    targets: list[str],
    min_train_year: int,
    output_dir: Path,
    use_db: bool = True,
    test_years: list[int] | None = None,
    min_history_years: int = 2,
) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)

    summary_rows: list[dict] = []
    all_fold_rows: list[dict] = []

    for target in targets:
        print(f"[target] {target} scope={scope}")
        df = build_ml_dataset(target=target, use_db=use_db, include_lags=True, scope=scope).copy()

        all_years = sorted([int(y) for y in df["year"].dropna().unique().tolist()])
        if test_years:
            eval_years = sorted([int(y) for y in test_years if int(y) in all_years])
        else:
            eval_years = [y for y in all_years if y > min_train_year]

        eval_years = [y for y in eval_years if len([h for h in all_years if min_train_year <= h < y]) >= min_history_years]
        if not eval_years:
            raise RuntimeError(
                f"No evaluable years for target={target}. "
                f"scope={scope}, min_train_year={min_train_year}, all_years={all_years}"
            )

        best = None
        best_fold_df = None
        for cfg in _candidate_configs_for_target(target, scope):
            is_anchor = cfg["model"] == "dept_nowcast_anchor"
            if cfg["feature_mode"] == "tuned":
                feature_list = [c for c in TUNED_FEATURES_BY_TARGET[target] if c in df.columns]
            elif cfg["feature_mode"] == "default":
                feature_list = _default_features(df, target)
            else:
                feature_list = []
            if not is_anchor and not feature_list:
                continue

            fold_cache = []
            for year in eval_years:
                train_df = df[(df["year"] < year) & (df["year"] >= int(min_train_year))].copy()
                test_df = df[df["year"] == year].copy()
                if train_df.empty or test_df.empty:
                    continue
                if train_df["year"].nunique() < min_history_years:
                    continue

                if is_anchor:
                    test_clean = test_df.copy()
                    test_clean["target"] = pd.to_numeric(test_clean.get("target"), errors="coerce")
                    test_clean = test_clean.dropna(subset=["target"]).copy()
                    if test_clean.empty:
                        continue
                    y_test = test_clean["target"].astype(float).values
                    baseline_col = _baseline_col_for_target(target)
                    if baseline_col in test_clean.columns:
                        baseline_test = _clip(pd.to_numeric(test_clean[baseline_col], errors="coerce").fillna(0.0).values)
                    else:
                        baseline_test = np.zeros(len(test_clean), dtype=float)
                    pred_model = _predict_from_dept_anchor(
                        test_clean,
                        target=target,
                        variant=str(cfg.get("anchor_variant", "level")),
                    )
                    if pred_model.size == 0:
                        continue
                else:
                    x_train, y_train, _ = _prepare_xy(train_df, target=target, feature_list=feature_list)
                    x_test, y_test, baseline_test = _prepare_xy(test_df, target=target, feature_list=feature_list)
                    if x_train.empty or x_test.empty:
                        continue

                    model = _make_model(cfg["model"])
                    model.fit(x_train, y_train)
                    pred_model = _clip(model.predict(x_test))

                fold_cache.append(
                    {
                        "year": int(year),
                        "actual": y_test,
                        "pred_model": pred_model,
                        "pred_baseline": baseline_test,
                    }
                )

            if not fold_cache:
                continue

            for alpha in [0.0, 0.25, 0.5, 0.75, 1.0]:
                fold_rows = []
                for fold in fold_cache:
                    pred_blend = _clip(alpha * fold["pred_model"] + (1.0 - alpha) * fold["pred_baseline"])
                    fold_rows.append(
                        {
                            "year": fold["year"],
                            "r2": float(r2_score(fold["actual"], pred_blend)),
                            "mae": float(mean_absolute_error(fold["actual"], pred_blend)),
                            "rmse": float(np.sqrt(mean_squared_error(fold["actual"], pred_blend))),
                            "model": cfg["model"],
                            "feature_mode": cfg["feature_mode"],
                            "anchor_variant": str(cfg.get("anchor_variant", "")),
                            "blend_alpha": float(alpha),
                        }
                    )

                fold_df = pd.DataFrame(fold_rows)
                row = {
                    "target": target,
                    "scope": scope,
                    "model": cfg["model"],
                    "feature_mode": cfg["feature_mode"],
                    "anchor_variant": str(cfg.get("anchor_variant", "")),
                    "blend_alpha": float(alpha),
                    "folds": int(len(fold_df)),
                    "r2_mean": float(fold_df["r2"].mean()),
                    "r2_min": float(fold_df["r2"].min()),
                    "r2_median": float(fold_df["r2"].median()),
                    "mae_mean": float(fold_df["mae"].mean()),
                    "rmse_mean": float(fold_df["rmse"].mean()),
                }
                if best is None or _score_key(row) > _score_key(best):
                    best = row
                    best_fold_df = fold_df

        if best is None or best_fold_df is None:
            raise RuntimeError(f"No valid configuration found for target={target}")

        variant_suffix = f" variant={best['anchor_variant']}" if str(best.get("anchor_variant", "")).strip() else ""
        print(
            f"  [best] model={best['model']} features={best['feature_mode']} "
            f"alpha={best['blend_alpha']:.2f}{variant_suffix} "
            f"r2_mean={best['r2_mean']:.4f} r2_min={best['r2_min']:.4f}"
        )

        # Save per-target details
        target_dir = output_dir / target
        target_dir.mkdir(parents=True, exist_ok=True)
        best_fold_df = best_fold_df.sort_values("year").reset_index(drop=True)
        fold_csv = target_dir / "fold_metrics.csv"
        best_json = target_dir / "best_config.json"
        best_fold_df.to_csv(fold_csv, index=False)
        with open(best_json, "w", encoding="utf-8") as f:
            json.dump(best, f, indent=2, ensure_ascii=False)

        best["fold_metrics_file"] = str(fold_csv)
        best["best_config_file"] = str(best_json)
        summary_rows.append(best)

        for r in best_fold_df.to_dict(orient="records"):
            all_fold_rows.append({"target": target, **r})

    summary_df = pd.DataFrame(summary_rows).sort_values("target").reset_index(drop=True)
    folds_df = pd.DataFrame(all_fold_rows).sort_values(["target", "year"]).reset_index(drop=True)

    summary_csv = output_dir / "reliable_summary.csv"
    folds_csv = output_dir / "reliable_folds.csv"
    summary_df.to_csv(summary_csv, index=False)
    folds_df.to_csv(folds_csv, index=False)

    all_positive_mean = bool((summary_df["r2_mean"] > 0).all()) if not summary_df.empty else False
    all_positive_min = bool((summary_df["r2_min"] > 0).all()) if not summary_df.empty else False
    print(f"[done] summary={summary_csv}")
    print(f"[done] folds={folds_csv}")
    print(f"[done] all_targets_r2_mean_gt_0={all_positive_mean}")
    print(f"[done] all_targets_r2_min_gt_0={all_positive_min}")

    return {
        "summary_csv": str(summary_csv),
        "folds_csv": str(folds_csv),
        "all_targets_r2_mean_gt_0": all_positive_mean,
        "all_targets_r2_min_gt_0": all_positive_min,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Optimisation fiabilite multi-annees/multi-partis par rolling CV."
    )
    parser.add_argument("--scope", choices=["departement", "commune"], default="commune")
    parser.add_argument(
        "--targets",
        type=str,
        default=",".join(DEFAULT_TARGETS),
        help="Cibles separees par virgules",
    )
    parser.add_argument(
        "--min-train-year",
        type=int,
        default=2012,
        help="Annee minimale incluse dans les jeux d'entrainement",
    )
    parser.add_argument(
        "--test-years",
        type=str,
        default="",
        help="Optionnel: annees d'evaluation (csv). Vide => toutes les annees evaluables",
    )
    parser.add_argument(
        "--min-history-years",
        type=int,
        default=2,
        help="Nombre minimal d'annees historiques avant un fold de test",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="data/processed/ml/reliable_all_years",
        help="Repertoire de sortie",
    )
    parser.add_argument(
        "--no-db",
        action="store_true",
        help="Utiliser l'ETL en memoire au lieu de la base PostgreSQL",
    )
    args = parser.parse_args()

    targets = [x.strip() for x in args.targets.split(",") if x.strip()]
    if args.test_years.strip():
        test_years = [int(x.strip()) for x in args.test_years.split(",") if x.strip()]
    else:
        test_years = None

    run_reliable_training(
        scope=args.scope,
        targets=targets,
        min_train_year=int(args.min_train_year),
        use_db=not args.no_db,
        test_years=test_years,
        min_history_years=int(args.min_history_years),
        output_dir=Path(args.output_dir),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
