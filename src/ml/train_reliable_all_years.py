from __future__ import annotations

import argparse
import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.exceptions import ConvergenceWarning
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

THEMATIC_FEATURE_PREFIXES = ("eco_", "edu_", "demo_", "env_")

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
    if model_name == "et_deep":
        return Pipeline(
            [
                ("scaler", StandardScaler()),
                (
                    "regressor",
                    ExtraTreesRegressor(
                        n_estimators=700,
                        max_depth=None,
                        min_samples_leaf=1,
                        random_state=42,
                        n_jobs=-1,
                    ),
                ),
            ]
        )
    if model_name == "rf_deep":
        return Pipeline(
            [
                ("scaler", StandardScaler()),
                (
                    "regressor",
                    RandomForestRegressor(
                        n_estimators=700,
                        max_depth=None,
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


def _make_residual_model(
    model_name: str = "ridge",
    alpha: float = 40.0,
    l1_ratio: float = 0.5,
    max_iter: int = 300,
    learning_rate: float = 0.03,
    max_depth: int = 4,
):
    # Conservative regularization to keep residual correction stable.
    if model_name == "ridge":
        return Pipeline([("scaler", StandardScaler()), ("regressor", Ridge(alpha=float(alpha), random_state=42))])
    if model_name == "enet":
        return Pipeline(
            [
                ("scaler", StandardScaler()),
                (
                    "regressor",
                    ElasticNet(
                        alpha=float(alpha),
                        l1_ratio=float(l1_ratio),
                        random_state=42,
                        max_iter=30000,
                    ),
                ),
            ]
        )
    if model_name == "hgb":
        return HistGradientBoostingRegressor(
            max_iter=int(max_iter),
            learning_rate=float(learning_rate),
            max_depth=int(max_depth),
            random_state=42,
        )
    raise ValueError(f"Unsupported residual model: {model_name}")


def _residual_candidate_configs() -> list[dict]:
    # Keep the grid compact to avoid very long runtimes while still exploring
    # linear and non-linear residual corrections.
    return [
        {"residual_model": "ridge", "residual_alpha": 12.0},
        {"residual_model": "ridge", "residual_alpha": 40.0},
        {"residual_model": "ridge", "residual_alpha": 120.0},
        {"residual_model": "enet", "residual_alpha": 0.005, "residual_l1_ratio": 0.3},
        {"residual_model": "enet", "residual_alpha": 0.02, "residual_l1_ratio": 0.6},
        {
            "residual_model": "hgb",
            "residual_max_iter": 250,
            "residual_learning_rate": 0.03,
            "residual_max_depth": 3,
        },
    ]


def _has_thematic_features(feature_list: list[str]) -> bool:
    return any(str(col).startswith(THEMATIC_FEATURE_PREFIXES) for col in feature_list)


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
    base_models = ["ridge", "enet", "rf", "et", "rf_deep", "et_deep", "gbr", "hgb"]
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
                {"model": "dept_nowcast_anchor_adaptive", "feature_mode": "anchor"},
            ]
        )
        # Anchor + residual correction model trained on full feature set,
        # including thematic tables (eco/edu/demo/env).
        for anchor_variant in ["level", "add", "mul"]:
            for beta in [0.01, 0.02, 0.05, 0.10]:
                for residual_cfg in _residual_candidate_configs():
                    configs.append(
                        {
                            "model": "dept_nowcast_anchor_residual",
                            "feature_mode": "default",
                            "anchor_variant": anchor_variant,
                            "residual_beta": float(beta),
                            **residual_cfg,
                        }
                    )
        for beta in [0.01, 0.02, 0.05, 0.10]:
            for residual_cfg in _residual_candidate_configs():
                configs.append(
                    {
                        "model": "dept_nowcast_anchor_adaptive_residual",
                        "feature_mode": "default",
                        "residual_beta": float(beta),
                        **residual_cfg,
                    }
                )
    return configs


def _score_key(row: dict) -> tuple[float, float, float, float, float]:
    # Prefer configurations with positive worst-fold R2 before maximizing means.
    all_folds_positive = 1.0 if float(row.get("r2_min", -1e9)) > 0 else 0.0
    uses_new_data = 1.0 if bool(row.get("uses_new_data", False)) else 0.0
    r2_min = float(row.get("r2_min", -1e9))
    r2_mean = float(row.get("r2_mean", -1e9))
    # Reliability first: prioritize worst-fold R2, then average R2.
    return (
        all_folds_positive,
        uses_new_data,
        r2_min,
        r2_mean,
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


def _predict_from_dept_anchor_adaptive(
    train_df: pd.DataFrame,
    predict_df: pd.DataFrame,
    target: str,
    fallback_variant: str = "mul",
) -> np.ndarray:
    """
    Adaptive anchor:
    - learns per-commune best variant among (level, add, mul) on train years
    - applies chosen variant to the prediction frame
    """
    if predict_df.empty:
        return np.array([], dtype=float)
    if "geo_code" not in predict_df.columns:
        return _predict_from_dept_anchor(predict_df, target=target, variant=fallback_variant)

    train_clean = train_df.copy()
    train_clean["target"] = pd.to_numeric(train_clean.get("target"), errors="coerce")
    train_clean = train_clean.dropna(subset=["target"]).copy()
    if train_clean.empty or "geo_code" not in train_clean.columns:
        return _predict_from_dept_anchor(predict_df, target=target, variant=fallback_variant)

    variants = ["level", "add", "mul"]
    train_err = train_clean[["geo_code"]].copy()
    for var in variants:
        pred_train = _predict_from_dept_anchor(train_clean, target=target, variant=var)
        train_err[f"err_{var}"] = np.abs(train_clean["target"].astype(float).values - pred_train)

    by_geo = train_err.groupby("geo_code", as_index=False)[[f"err_{v}" for v in variants]].mean()
    err_matrix = by_geo[[f"err_{v}" for v in variants]].to_numpy(dtype=float)
    best_idx = np.argmin(err_matrix, axis=1)
    by_geo["best_variant"] = [variants[i] for i in best_idx]
    best_map = dict(zip(by_geo["geo_code"].astype(str), by_geo["best_variant"].astype(str)))

    pred_clean = predict_df.copy()
    pred_clean["target"] = pd.to_numeric(pred_clean.get("target"), errors="coerce")
    pred_clean = pred_clean.dropna(subset=["target"]).copy()
    if pred_clean.empty:
        return np.array([], dtype=float)

    pred_by_variant = {
        var: _predict_from_dept_anchor(pred_clean, target=target, variant=var)
        for var in variants
    }
    geo_values = pred_clean["geo_code"].astype(str).tolist()
    chosen_variants = [best_map.get(g, fallback_variant) for g in geo_values]

    out = np.zeros(len(pred_clean), dtype=float)
    for i, chosen in enumerate(chosen_variants):
        chosen_key = chosen if chosen in pred_by_variant else fallback_variant
        out[i] = pred_by_variant[chosen_key][i]
    return _clip(out)


def run_reliable_training(
    scope: str,
    targets: list[str],
    min_train_year: int,
    output_dir: Path,
    use_db: bool = True,
    test_years: list[int] | None = None,
    min_history_years: int = 2,
) -> dict:
    warnings.filterwarnings("ignore", category=ConvergenceWarning)
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
            is_anchor_adaptive = cfg["model"] == "dept_nowcast_anchor_adaptive"
            is_anchor_residual = cfg["model"] == "dept_nowcast_anchor_residual"
            is_anchor_adaptive_residual = cfg["model"] == "dept_nowcast_anchor_adaptive_residual"
            if cfg["feature_mode"] == "tuned":
                feature_list = [c for c in TUNED_FEATURES_BY_TARGET[target] if c in df.columns]
            elif cfg["feature_mode"] == "default":
                feature_list = _default_features(df, target)
            else:
                feature_list = []
            if not is_anchor and not is_anchor_adaptive and not feature_list:
                continue
            uses_new_data_cfg = (
                is_anchor_residual
                or is_anchor_adaptive_residual
                or _has_thematic_features(feature_list)
                or bool(cfg.get("feature_mode") == "tuned")
            )

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
                elif is_anchor_adaptive:
                    train_clean = train_df.copy()
                    train_clean["target"] = pd.to_numeric(train_clean.get("target"), errors="coerce")
                    train_clean = train_clean.dropna(subset=["target"]).copy()
                    test_clean = test_df.copy()
                    test_clean["target"] = pd.to_numeric(test_clean.get("target"), errors="coerce")
                    test_clean = test_clean.dropna(subset=["target"]).copy()
                    if train_clean.empty or test_clean.empty:
                        continue

                    y_test = test_clean["target"].astype(float).values
                    baseline_col = _baseline_col_for_target(target)
                    if baseline_col in test_clean.columns:
                        baseline_test = _clip(pd.to_numeric(test_clean[baseline_col], errors="coerce").fillna(0.0).values)
                    else:
                        baseline_test = np.zeros(len(test_clean), dtype=float)
                    pred_model = _predict_from_dept_anchor_adaptive(
                        train_clean,
                        test_clean,
                        target=target,
                        fallback_variant="mul",
                    )
                    if pred_model.size == 0:
                        continue
                elif is_anchor_residual:
                    train_clean = train_df.copy()
                    train_clean["target"] = pd.to_numeric(train_clean.get("target"), errors="coerce")
                    train_clean = train_clean.dropna(subset=["target"]).copy()
                    test_clean = test_df.copy()
                    test_clean["target"] = pd.to_numeric(test_clean.get("target"), errors="coerce")
                    test_clean = test_clean.dropna(subset=["target"]).copy()
                    if train_clean.empty or test_clean.empty:
                        continue

                    x_train, y_train, _ = _prepare_xy(train_clean, target=target, feature_list=feature_list)
                    x_test, y_test, baseline_test = _prepare_xy(test_clean, target=target, feature_list=feature_list)
                    if x_train.empty or x_test.empty:
                        continue

                    anchor_variant = str(cfg.get("anchor_variant", "level"))
                    anchor_train = _predict_from_dept_anchor(train_clean, target=target, variant=anchor_variant)
                    anchor_test = _predict_from_dept_anchor(test_clean, target=target, variant=anchor_variant)
                    if anchor_train.size != len(y_train) or anchor_test.size != len(y_test):
                        continue

                    residual_model = _make_residual_model(
                        model_name=str(cfg.get("residual_model", "ridge")),
                        alpha=float(cfg.get("residual_alpha", 40.0)),
                        l1_ratio=float(cfg.get("residual_l1_ratio", 0.5)),
                        max_iter=int(cfg.get("residual_max_iter", 300)),
                        learning_rate=float(cfg.get("residual_learning_rate", 0.03)),
                        max_depth=int(cfg.get("residual_max_depth", 4)),
                    )
                    residual_model.fit(x_train, y_train - anchor_train)
                    residual_pred = residual_model.predict(x_test)
                    beta = float(cfg.get("residual_beta", 0.05))
                    pred_model = _clip(anchor_test + beta * residual_pred)
                elif is_anchor_adaptive_residual:
                    train_clean = train_df.copy()
                    train_clean["target"] = pd.to_numeric(train_clean.get("target"), errors="coerce")
                    train_clean = train_clean.dropna(subset=["target"]).copy()
                    test_clean = test_df.copy()
                    test_clean["target"] = pd.to_numeric(test_clean.get("target"), errors="coerce")
                    test_clean = test_clean.dropna(subset=["target"]).copy()
                    if train_clean.empty or test_clean.empty:
                        continue

                    x_train, y_train, _ = _prepare_xy(train_clean, target=target, feature_list=feature_list)
                    x_test, y_test, baseline_test = _prepare_xy(test_clean, target=target, feature_list=feature_list)
                    if x_train.empty or x_test.empty:
                        continue

                    anchor_train = _predict_from_dept_anchor_adaptive(
                        train_clean,
                        train_clean,
                        target=target,
                        fallback_variant="mul",
                    )
                    anchor_test = _predict_from_dept_anchor_adaptive(
                        train_clean,
                        test_clean,
                        target=target,
                        fallback_variant="mul",
                    )
                    if anchor_train.size != len(y_train) or anchor_test.size != len(y_test):
                        continue

                    residual_model = _make_residual_model(
                        model_name=str(cfg.get("residual_model", "ridge")),
                        alpha=float(cfg.get("residual_alpha", 40.0)),
                        l1_ratio=float(cfg.get("residual_l1_ratio", 0.5)),
                        max_iter=int(cfg.get("residual_max_iter", 300)),
                        learning_rate=float(cfg.get("residual_learning_rate", 0.03)),
                        max_depth=int(cfg.get("residual_max_depth", 4)),
                    )
                    residual_model.fit(x_train, y_train - anchor_train)
                    residual_pred = residual_model.predict(x_test)
                    beta = float(cfg.get("residual_beta", 0.05))
                    pred_model = _clip(anchor_test + beta * residual_pred)
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

            alpha_grid = (
                [0.75, 0.9, 1.0]
                if (is_anchor_residual or is_anchor_adaptive_residual)
                else [0.0, 0.25, 0.5, 0.75, 1.0]
            )
            for alpha in alpha_grid:
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
                            "residual_beta": float(cfg.get("residual_beta", 0.0)),
                            "residual_model": str(cfg.get("residual_model", "")),
                            "residual_alpha": float(cfg.get("residual_alpha", 0.0)),
                            "residual_l1_ratio": float(cfg.get("residual_l1_ratio", 0.0)),
                            "residual_max_iter": int(cfg.get("residual_max_iter", 0)),
                            "residual_learning_rate": float(cfg.get("residual_learning_rate", 0.0)),
                            "residual_max_depth": int(cfg.get("residual_max_depth", 0)),
                            "uses_new_data": bool(uses_new_data_cfg),
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
                    "residual_beta": float(cfg.get("residual_beta", 0.0)),
                    "residual_model": str(cfg.get("residual_model", "")),
                    "residual_alpha": float(cfg.get("residual_alpha", 0.0)),
                    "residual_l1_ratio": float(cfg.get("residual_l1_ratio", 0.0)),
                    "residual_max_iter": int(cfg.get("residual_max_iter", 0)),
                    "residual_learning_rate": float(cfg.get("residual_learning_rate", 0.0)),
                    "residual_max_depth": int(cfg.get("residual_max_depth", 0)),
                    "uses_new_data": bool(uses_new_data_cfg),
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
        beta_suffix = (
            f" beta={best['residual_beta']:.2f}"
            if float(best.get("residual_beta", 0.0)) > 0.0
            else ""
        )
        residual_suffix = ""
        if str(best.get("residual_model", "")).strip():
            residual_suffix = (
                f" residual={best['residual_model']}"
                f" alpha={best.get('residual_alpha', 0.0):.4f}"
            )
            if float(best.get("residual_l1_ratio", 0.0)) > 0.0:
                residual_suffix += f" l1={best['residual_l1_ratio']:.2f}"
            if int(best.get("residual_max_depth", 0)) > 0:
                residual_suffix += f" depth={int(best['residual_max_depth'])}"
        print(
            f"  [best] model={best['model']} features={best['feature_mode']} "
            f"alpha={best['blend_alpha']:.2f}{variant_suffix}{beta_suffix}{residual_suffix} "
            f"uses_new_data={bool(best.get('uses_new_data', False))} "
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
