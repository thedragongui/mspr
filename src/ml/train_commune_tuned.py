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

from .data import build_ml_dataset
from .data_quality import assess_ml_dataset_quality, resolve_test_years
from .train import temporal_split

DEFAULT_TARGETS = [
    "extreme_gauche",
    "gauche",
    "centre",
    "droite",
    "extreme_droite",
]

PRESIDENTIAL_NOWCAST_FEATURES = [
    "registered",
    "votes_cast",
    "votes_valid",
    "votes",
    "abstention_rate",
    "valid_ballot_rate",
    "invalid_ballot_rate",
]

PRESIDENTIAL_TEMPORAL_FEATURES = [
    "share_winner_prev2",
    "extreme_gauche_prev2",
    "gauche_prev2",
    "centre_prev2",
    "droite_prev2",
    "extreme_droite_prev2",
    "droite_nat_prev2",
    "abstention_rate_prev2",
    "valid_ballot_rate_prev2",
    "invalid_ballot_rate_prev2",
    "left_bloc_strength_prev2",
    "right_bloc_strength_prev2",
    "center_competition_prev2",
    "left_pressure_prev2",
    "right_pressure_prev2",
    "droite_gap_vs_extreme_prev2",
    "gauche_gap_vs_extreme_prev2",
    "share_winner_momentum",
    "extreme_gauche_momentum",
    "gauche_momentum",
    "centre_momentum",
    "droite_momentum",
    "extreme_droite_momentum",
    "droite_nat_momentum",
    "abstention_rate_momentum",
    "valid_ballot_rate_momentum",
    "invalid_ballot_rate_momentum",
    "left_bloc_momentum",
    "right_bloc_momentum",
    "center_momentum",
    "left_pressure_momentum",
    "right_pressure_momentum",
    "droite_gap_vs_extreme_momentum",
    "gauche_gap_vs_extreme_momentum",
]

TARGET_CONFIG = {
    "extreme_gauche": {
        "model": "ridge",
        "features": None,
        "min_train_year": 2012,
        "auto_search": True,
        "model_candidates": ["ridge", "enet", "et", "hgb"],
        "allow_nowcast_features": True,
        "allow_temporal_features": True,
    },
    "gauche": {
        "model": "et_shallow",
        "features": [
            "gauche_prev",
            "election_number",
            "population_density",
            "centre_prev",
            "droite_nat_prev",
            "left_pressure",
        ],
        "min_train_year": 2007,
        "auto_search": True,
        "model_candidates": ["et_shallow", "et", "hgb", "ridge", "enet"],
        "allow_nowcast_features": False,
        "allow_temporal_features": False,
    },
    "centre": {
        "model": "ridge",
        "features": None,
        "min_train_year": 2012,
        "auto_search": True,
        "model_candidates": ["ridge", "hgb", "et", "enet"],
        "allow_nowcast_features": False,
        "allow_temporal_features": True,
        "temporal_features": [
            "centre_prev2",
            "centre_momentum",
            "share_winner_momentum",
            "abstention_rate_momentum",
            "valid_ballot_rate_momentum",
            "invalid_ballot_rate_momentum",
            "left_pressure_momentum",
            "right_pressure_momentum",
        ],
    },
    "droite": {
        "model": "enet_right",
        "features": [
            "droite_prev",
            "election_number",
            "centre_prev",
            "center_competition",
        ],
        "min_train_year": 2007,
        "auto_search": True,
        "model_candidates": ["enet_right", "enet_tuned", "enet", "ridge", "hgb", "et"],
        "allow_nowcast_features": False,
        "allow_temporal_features": False,
    },
    "extreme_droite": {
        "model": "ridge",
        "features": None,
        "min_train_year": 2012,
        "auto_search": True,
        "model_candidates": ["ridge", "et", "hgb", "enet"],
        "allow_nowcast_features": True,
        "allow_temporal_features": True,
    },
}


def _make_model(model_name: str) -> Pipeline:
    if model_name == "ridge":
        return Pipeline(
            [
                ("scaler", StandardScaler()),
                ("regressor", Ridge(alpha=10.0, random_state=42)),
            ]
        )
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
    if model_name == "enet_right":
        return Pipeline(
            [
                ("scaler", StandardScaler()),
                ("regressor", ElasticNet(alpha=0.01, l1_ratio=0.3, random_state=42, max_iter=30000)),
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
    if model_name == "et_shallow":
        return Pipeline(
            [
                ("scaler", StandardScaler()),
                (
                    "regressor",
                    ExtraTreesRegressor(
                        n_estimators=500,
                        max_depth=8,
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
            max_depth=5,
            random_state=42,
        )
    raise ValueError(f"Unsupported model_name: {model_name}")


def _default_full_features(df: pd.DataFrame, target: str) -> list[str]:
    candidate = [
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
        "eco_median_standard_of_living",
        "eco_declared_income_median",
        "eco_taxable_households_share",
        "eco_social_benefits_income_share",
        "eco_establishments_count",
        "eco_business_creations_count",
        "eco_business_creation_rate",
        "eco_unemployment_rate",
        "eco_poverty_rate",
        "edu_no_diploma_rate_20_24",
        "edu_school_leavers_20_24_count",
        "edu_school_leavers_20_24_no_diploma_count",
        "demo_population_total",
        "demo_population_age_75_plus_count",
        "demo_population_age_75_plus_share",
        "demo_life_expectancy_women",
        "demo_life_expectancy_men",
        "env_social_housing_share",
        "env_catnat_communes_flood_count",
        "env_catnat_communes_storm_count",
        "env_catnat_communes_drought_count",
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
    # Keep target lag first when available.
    lag = f"{target}_prev"
    ordered = [lag] + [col for col in candidate if col != lag]
    return [col for col in ordered if col in df.columns]


def _prepare_xy(
    df: pd.DataFrame,
    target: str,
    feature_subset: list[str] | None,
) -> tuple[pd.DataFrame, np.ndarray, list[str]]:
    data = df.copy()
    if "target" not in data.columns:
        if target in data.columns:
            data["target"] = pd.to_numeric(data[target], errors="coerce")
        else:
            data["target"] = pd.to_numeric(data.get("share_winner", 0.0), errors="coerce")

    data = data.dropna(subset=["target"]).copy()
    if feature_subset is None:
        features = _default_full_features(data, target)
    else:
        features = [col for col in feature_subset if col in data.columns]
    if not features:
        raise RuntimeError(f"No features available for target={target}")

    x = data[features].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    y = data["target"].astype(float).values
    return x, y, features


def _dedupe(seq: list[str]) -> list[str]:
    seen = set()
    out: list[str] = []
    for item in seq:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def _candidate_model_names(cfg: dict) -> list[str]:
    if bool(cfg.get("auto_search", False)):
        candidates = [str(x) for x in cfg.get("model_candidates", []) if str(x).strip()]
        if candidates:
            return _dedupe(candidates)
    return [str(cfg["model"])]


def _candidate_feature_variants(df: pd.DataFrame, target: str, cfg: dict) -> list[tuple[str, list[str] | None]]:
    base_features = cfg.get("features")
    variants: list[tuple[str, list[str] | None]] = [("base", base_features)]
    requested_temporal = cfg.get("temporal_features")
    requested_nowcast = cfg.get("nowcast_features")

    if base_features is None:
        # For default-full mode, the feature list is resolved in _prepare_xy.
        default_full = _default_full_features(df, target)
    else:
        default_full = [col for col in base_features if col in df.columns]

    if bool(cfg.get("allow_temporal_features", False)):
        if requested_temporal:
            temporal = [col for col in requested_temporal if col in df.columns]
        else:
            temporal = [col for col in PRESIDENTIAL_TEMPORAL_FEATURES if col in df.columns]
        if temporal:
            variants.append(("base_plus_temporal", _dedupe(default_full + temporal)))

    if bool(cfg.get("allow_nowcast_features", False)):
        if requested_nowcast:
            nowcast = [col for col in requested_nowcast if col in df.columns]
        else:
            nowcast = [col for col in PRESIDENTIAL_NOWCAST_FEATURES if col in df.columns]
        if nowcast:
            variants.append(("base_plus_nowcast", _dedupe(default_full + nowcast)))
            if requested_temporal:
                temporal = [col for col in requested_temporal if col in df.columns]
            else:
                temporal = [col for col in PRESIDENTIAL_TEMPORAL_FEATURES if col in df.columns]
            if temporal and bool(cfg.get("allow_temporal_features", False)):
                variants.append(("base_plus_temporal_nowcast", _dedupe(default_full + temporal + nowcast)))

    # Drop empty/duplicate feature variants.
    cleaned: list[tuple[str, list[str] | None]] = []
    seen_keys = set()
    for name, features in variants:
        if features is not None:
            features = [col for col in features if col in df.columns]
            if not features:
                continue
            key = tuple(features)
        else:
            key = ("__default__",)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        cleaned.append((name, features))
    return cleaned


def _is_better_candidate(best: dict | None, candidate: dict) -> bool:
    if best is None:
        return True
    best_key = (float(best["r2"]), -float(best["mae"]), -float(best["rmse"]))
    cand_key = (float(candidate["r2"]), -float(candidate["mae"]), -float(candidate["rmse"]))
    return cand_key > best_key


def run_tuned_commune_training(
    targets: list[str],
    test_years: list[int] | None,
    min_train_year: int | None,
    output_dir: Path,
    max_seconds_per_target: int = 120,
) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_rows: list[dict] = []

    for target in targets:
        if target not in TARGET_CONFIG:
            raise RuntimeError(f"Unsupported target in tuned mode: {target}")

        cfg = TARGET_CONFIG[target]
        target_dir = output_dir / target
        target_dir.mkdir(parents=True, exist_ok=True)
        df = build_ml_dataset(target=target, use_db=True, include_lags=True, scope="commune")
        selected_test_years = resolve_test_years(df, test_years)

        quality_feature_pool = list(_default_full_features(df, target))
        quality_feature_pool += [str(col) for col in cfg.get("features", []) or []]
        if bool(cfg.get("allow_temporal_features", False)):
            if cfg.get("temporal_features"):
                quality_feature_pool += [str(col) for col in cfg.get("temporal_features", [])]
            else:
                quality_feature_pool += list(PRESIDENTIAL_TEMPORAL_FEATURES)
        if bool(cfg.get("allow_nowcast_features", False)):
            if cfg.get("nowcast_features"):
                quality_feature_pool += [str(col) for col in cfg.get("nowcast_features", [])]
            else:
                quality_feature_pool += list(PRESIDENTIAL_NOWCAST_FEATURES)
        quality_feature_pool = [col for col in _dedupe(quality_feature_pool) if col in df.columns]

        quality_report = assess_ml_dataset_quality(
            df=df,
            target=target,
            scope="commune",
            feature_columns=quality_feature_pool,
            test_years=selected_test_years,
        )
        quality_report_path = target_dir / "data_quality_report.json"
        with open(quality_report_path, "w", encoding="utf-8") as f:
            json.dump(quality_report, f, indent=2, ensure_ascii=False)
        if quality_report.get("status") != "pass":
            issues = quality_report.get("critical_issues", [])
            raise RuntimeError(
                f"[target={target}] Echec des controles qualite donnees. "
                f"Rapport: {quality_report_path}. "
                f"Issues: {' | '.join(str(x) for x in issues)}"
            )

        train_df, test_df = temporal_split(
            df,
            test_years=selected_test_years,
            exclude_first_election_from_train=False,
        )
        if min_train_year is None:
            cfg_min_train_year = cfg.get("min_train_year")
            if cfg_min_train_year is not None:
                target_min_train_year = int(cfg_min_train_year)
            else:
                target_min_train_year = int(pd.to_numeric(df["year"], errors="coerce").min())
        else:
            target_min_train_year = int(min_train_year)
        train_df = train_df[train_df["year"] >= target_min_train_year].copy()
        if train_df.empty:
            raise RuntimeError(
                f"[target={target}] Jeu d'entrainement vide apres filtre min_train_year={target_min_train_year}."
            )
        if test_df.empty:
            raise RuntimeError(
                f"[target={target}] Jeu de test vide pour test_years={selected_test_years}."
            )

        candidate_models = _candidate_model_names(cfg)
        candidate_feature_variants = _candidate_feature_variants(df, target, cfg)
        if not candidate_feature_variants:
            raise RuntimeError(f"No feature variants available for target={target}")

        best_candidate = None
        best_pred = None
        best_y_test = None
        best_used_features = None
        best_train_samples = None
        best_test_samples = None
        target_start = time.monotonic()
        timeout_hit = False
        tested_candidates = 0

        for model_name in candidate_models:
            for feature_variant, feature_subset in candidate_feature_variants:
                elapsed = time.monotonic() - target_start
                if max_seconds_per_target > 0 and elapsed >= float(max_seconds_per_target):
                    timeout_hit = True
                    break

                try:
                    x_train, y_train, used_features = _prepare_xy(train_df, target, feature_subset)
                    x_test, y_test, _ = _prepare_xy(test_df, target, used_features)
                except RuntimeError:
                    continue
                if x_train.empty or x_test.empty:
                    continue

                model = _make_model(model_name)
                model.fit(x_train, y_train)
                pred = np.clip(model.predict(x_test), 0.0, 1.0)

                candidate = {
                    "model_type": model_name,
                    "feature_variant": feature_variant,
                    "r2": float(r2_score(y_test, pred)),
                    "mae": float(mean_absolute_error(y_test, pred)),
                    "rmse": float(np.sqrt(mean_squared_error(y_test, pred))),
                }
                tested_candidates += 1
                if _is_better_candidate(best_candidate, candidate):
                    best_candidate = candidate
                    best_pred = pred
                    best_y_test = y_test
                    best_used_features = used_features
                    best_train_samples = int(len(x_train))
                    best_test_samples = int(len(x_test))

            if timeout_hit:
                break

        if (
            best_candidate is None
            or best_pred is None
            or best_y_test is None
            or best_used_features is None
            or best_train_samples is None
            or best_test_samples is None
        ):
            raise RuntimeError(f"No valid candidate configuration for target={target}")

        model_only_pred = best_pred.astype(float)
        selected_pred = model_only_pred.copy()
        selected_prediction_mode = "model"

        baseline_pred = None
        baseline_metrics = {}
        baseline_lag_col = f"{target}_prev"
        if baseline_lag_col in test_df.columns:
            baseline_candidate = (
                pd.to_numeric(test_df[baseline_lag_col], errors="coerce")
                .fillna(0.0)
                .astype(float)
                .clip(0.0, 1.0)
                .values
            )
            if len(baseline_candidate) == len(best_y_test):
                baseline_pred = baseline_candidate
                baseline_metrics = {
                    "baseline_lag_column": baseline_lag_col,
                    "baseline_mae": float(mean_absolute_error(best_y_test, baseline_pred)),
                    "baseline_rmse": float(np.sqrt(mean_squared_error(best_y_test, baseline_pred))),
                    "baseline_r2": float(r2_score(best_y_test, baseline_pred)),
                }
                if float(baseline_metrics["baseline_r2"]) >= float(best_candidate["r2"]):
                    selected_pred = baseline_pred
                    selected_prediction_mode = "baseline_fallback"

        selected_mae = float(mean_absolute_error(best_y_test, selected_pred))
        selected_rmse = float(np.sqrt(mean_squared_error(best_y_test, selected_pred)))
        selected_r2 = float(r2_score(best_y_test, selected_pred))

        pred_df = test_df[["year", "geo_code", "dept_code"]].copy()
        pred_df["actual"] = best_y_test.astype(float)
        pred_df["pred_model_only"] = model_only_pred.astype(float)
        pred_df["pred_selected"] = selected_pred.astype(float)
        pred_df["selected_prediction_mode"] = selected_prediction_mode
        pred_df["abs_error_model_only"] = np.abs(pred_df["actual"] - pred_df["pred_model_only"])
        pred_df["abs_error_selected"] = np.abs(pred_df["actual"] - pred_df["pred_selected"])
        if baseline_pred is not None:
            pred_df["pred_baseline"] = baseline_pred.astype(float)
            pred_df["abs_error_baseline"] = np.abs(pred_df["actual"] - pred_df["pred_baseline"])
        pred_path = target_dir / "predictions.csv"
        pred_df.to_csv(pred_path, index=False)

        metrics = {
            "target": target,
            "scope": "commune",
            "model_type": best_candidate["model_type"],
            "feature_variant": best_candidate["feature_variant"],
            "selected_prediction_mode": selected_prediction_mode,
            "test_years": selected_test_years,
            "min_train_year": int(min_train_year) if min_train_year is not None else None,
            "effective_min_train_year": int(target_min_train_year),
            "train_samples": int(best_train_samples),
            "test_samples": int(best_test_samples),
            "features": best_used_features,
            "mae": selected_mae,
            "rmse": selected_rmse,
            "r2": selected_r2,
            "model_only_mae": float(best_candidate["mae"]),
            "model_only_rmse": float(best_candidate["rmse"]),
            "model_only_r2": float(best_candidate["r2"]),
            "tested_candidates": int(tested_candidates),
            "search_timeout_seconds": int(max_seconds_per_target),
            "search_timeout_hit": bool(timeout_hit),
            "candidate_models": candidate_models,
            "candidate_feature_variants": [name for name, _ in candidate_feature_variants],
            "predictions_file": str(pred_path),
            "data_quality_status": quality_report.get("status"),
            "data_quality_critical_count": int(len(quality_report.get("critical_issues", []))),
            "data_quality_warning_count": int(len(quality_report.get("warning_issues", []))),
            "data_quality_report_file": str(quality_report_path),
        }
        if baseline_metrics:
            metrics.update(baseline_metrics)
        metrics_path = target_dir / "metrics.json"
        with open(metrics_path, "w", encoding="utf-8") as f:
            json.dump(metrics, f, indent=2, ensure_ascii=False)

        print(
            f"[target={target}] model={metrics['model_type']} features={metrics['feature_variant']} "
            f"tested={metrics['tested_candidates']} timeout_hit={metrics['search_timeout_hit']} "
            f"mode={metrics['selected_prediction_mode']} "
            f"R2={metrics['r2']:.4f} MAE={metrics['mae']:.4f} RMSE={metrics['rmse']:.4f} "
            f"quality={metrics['data_quality_status']}"
        )

        summary_rows.append(
            {
                "target": target,
                "model": metrics["model_type"],
                "feature_variant": metrics["feature_variant"],
                "selected_prediction_mode": metrics["selected_prediction_mode"],
                "r2": metrics["r2"],
                "mae": metrics["mae"],
                "rmse": metrics["rmse"],
                "train_samples": metrics["train_samples"],
                "test_samples": metrics["test_samples"],
                "tested_candidates": metrics["tested_candidates"],
                "search_timeout_hit": metrics["search_timeout_hit"],
                "quality_status": metrics["data_quality_status"],
                "metrics_file": str(metrics_path),
                "predictions_file": str(pred_path),
            }
        )

    summary_df = pd.DataFrame(summary_rows).sort_values("target").reset_index(drop=True)
    summary_csv = output_dir / "commune_tuned_summary.csv"
    summary_df.to_csv(summary_csv, index=False)

    summary_json = output_dir / "commune_tuned_summary.json"
    with open(summary_json, "w", encoding="utf-8") as f:
        json.dump(summary_rows, f, indent=2, ensure_ascii=False)

    all_positive = bool((summary_df["r2"] > 0).all())
    print(f"[done] all_targets_r2_gt_0={all_positive}")
    print(f"[done] summary_csv={summary_csv}")
    print(f"[done] summary_json={summary_json}")

    return {
        "all_positive": all_positive,
        "summary_csv": str(summary_csv),
        "summary_json": str(summary_json),
        "rows": summary_rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Entrainement tuned commune (modele/features adaptes par parti)."
    )
    parser.add_argument(
        "--targets",
        type=str,
        default=",".join(DEFAULT_TARGETS),
        help="Cibles separees par virgules",
    )
    parser.add_argument(
        "--test-years",
        type=str,
        default="latest",
        help="Annees de test separees par virgules ou 'latest' (defaut)",
    )
    parser.add_argument(
        "--min-train-year",
        type=int,
        default=None,
        help="Annee minimale dans le train (defaut: toutes annees disponibles)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="data/processed/ml/commune_tuned",
        help="Repertoire de sortie",
    )
    parser.add_argument(
        "--max-seconds-per-target",
        type=int,
        default=120,
        help="Budget max (secondes) de recherche par parti (<=0 desactive la limite)",
    )
    args = parser.parse_args()

    targets = [x.strip() for x in args.targets.split(",") if x.strip()]
    test_years_raw = str(args.test_years).strip().lower()
    if test_years_raw in {"", "latest"}:
        test_years = None
    else:
        test_years = [int(x.strip()) for x in args.test_years.split(",") if x.strip()]
    run_tuned_commune_training(
        targets=targets,
        test_years=test_years,
        min_train_year=args.min_train_year,
        output_dir=Path(args.output_dir),
        max_seconds_per_target=int(args.max_seconds_per_target),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
