"""
EntraÃƒÂ®nement du modÃƒÂ¨le prÃƒÂ©dictif supervisÃƒÂ© : rÃƒÂ©gression de la part de vote (gagnant ou famille).
Split temporel pour ÃƒÂ©viter le data leakage ; ÃƒÂ©valuation sur les derniÃƒÂ¨res ÃƒÂ©lections.
"""
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

from .data import (
    SOCIO_INDICATORS,
    FAMILIES,
    ELECTION_CONTEXT_FEATURES,
    COMMUNE_GEO_FEATURES,
    build_ml_dataset,
)

# RÃƒÂ©pertoire de sortie des artefacts ML
DEFAULT_OUTPUT_DIR = Path("data/processed/ml")
MODEL_FILENAME = "model.joblib"
METRICS_FILENAME = "metrics.json"
PREDICTIONS_FILENAME = "predictions.csv"


# Sous-ensemble de features "noyau" (sujet: indicateurs fortement corrÃƒÂ©lÃƒÂ©s aux rÃƒÂ©sultats)
CORE_SOCIO = ["unemployment_rate", "poverty_rate", "turnout_rate"]
CORE_LAGS = ["share_winner_prev", "extreme_droite_prev", "gauche_prev", "droite_prev"]
CORE_COMMUNE_GEO = ["population_density", "population_log"]

# Pour rapprocher le RÃ‚Â² de 0 : on privilÃƒÂ©gie le lag de la cible + peu de features (ÃƒÂ©vite sur-apprentissage)
TARGET_TO_LAG = {
    "share_winner": "share_winner_prev",
    "extreme_droite": "extreme_droite_prev",
    "gauche": "gauche_prev",
    "droite": "droite_prev",
    "centre": "centre_prev",
}
DEFAULT_BASELINE_LAG = "share_winner_prev"


def get_baseline_lag_column(target: str | None = None) -> str:
    """Return the lag column used for the naive baseline prediction."""
    if target:
        return TARGET_TO_LAG.get(target, DEFAULT_BASELINE_LAG)
    return DEFAULT_BASELINE_LAG


def _clip_vote_shares(values: np.ndarray) -> np.ndarray:
    """Keep predicted vote shares in [0, 1]."""
    return np.clip(values.astype(float), 0.0, 1.0)


def _extract_baseline_predictions(df_clean: pd.DataFrame, target: str | None = None) -> np.ndarray | None:
    """Extract baseline predictions from the lag column for the selected target."""
    lag_col = get_baseline_lag_column(target)
    if lag_col not in df_clean.columns:
        return None
    baseline = pd.to_numeric(df_clean[lag_col], errors="coerce").fillna(0.0).values
    return _clip_vote_shares(baseline)


def _walk_forward_validation_years(
    train_df: pd.DataFrame,
    max_folds: int = 3,
    min_history_years: int = 3,
) -> list[int]:
    """
    Pick walk-forward validation years from the train period only.
    Each validation year must have enough historical years before it.
    """
    years = sorted(train_df["year"].unique())
    valid = []
    for year in years:
        history = [y for y in years if y < year]
        if len(history) >= min_history_years:
            valid.append(year)
    return valid[-max_folds:]


def _evaluate_model_vs_baseline_on_train(
    train_df: pd.DataFrame,
    target: str,
    model_type: str,
    alpha: float,
    max_depth: int,
    use_core_only: bool,
    minimal_for_stable_r2: bool,
) -> dict:
    """
    Walk-forward validation (train period only) to compare model vs naive lag baseline.
    """
    model_maes, baseline_maes = [], []
    fold_rows = []
    val_years = _walk_forward_validation_years(train_df)

    for val_year in val_years:
        fold_train = train_df[train_df["year"] < val_year]
        fold_val = train_df[train_df["year"] == val_year]
        if fold_train.empty or fold_val.empty:
            continue

        X_train, y_train, _, _ = prepare_xy(
            fold_train,
            use_core_only=use_core_only,
            target=target,
            minimal_for_stable_r2=minimal_for_stable_r2,
        )
        X_val, y_val, _, val_clean = prepare_xy(
            fold_val,
            use_core_only=use_core_only,
            target=target,
            minimal_for_stable_r2=minimal_for_stable_r2,
        )
        if X_train.empty or X_val.empty or len(X_train) < 10:
            continue

        model = _make_model(model_type, alpha=alpha, max_depth=max_depth)
        model.fit(X_train, y_train)
        model_pred = _clip_vote_shares(model.predict(X_val))
        model_mae = float(mean_absolute_error(y_val, model_pred))
        model_maes.append(model_mae)

        baseline_pred = _extract_baseline_predictions(val_clean, target=target)
        baseline_mae = None
        if baseline_pred is not None:
            baseline_mae = float(mean_absolute_error(y_val, baseline_pred))
            baseline_maes.append(baseline_mae)

        fold_rows.append(
            {
                "year": int(val_year),
                "model_mae": model_mae,
                "baseline_mae": baseline_mae,
            }
        )

    latest = fold_rows[-1] if fold_rows else {}

    return {
        "validation_years": [int(year) for year in val_years],
        "validation_folds": len(model_maes),
        "validation_model_mae_mean": float(np.mean(model_maes)) if model_maes else None,
        "validation_baseline_mae_mean": float(np.mean(baseline_maes)) if baseline_maes else None,
        "validation_latest_year": latest.get("year"),
        "validation_model_mae_latest": latest.get("model_mae"),
        "validation_baseline_mae_latest": latest.get("baseline_mae"),
    }


def _reliability_label(
    r2: float,
    mae: float,
    baseline_r2: float | None,
    baseline_mae: float | None,
) -> str:
    """Simple reliability label for downstream reporting."""
    if baseline_mae is not None:
        if r2 >= 0.0 and mae <= baseline_mae:
            return "high"
        if mae <= baseline_mae * 1.05:
            return "medium"
        return "low"
    if r2 >= 0.0:
        return "medium"
    return "low"


def _select_ridge_alpha_on_latest_history(
    train_df: pd.DataFrame,
    target: str,
    use_core_only: bool,
    minimal_for_stable_r2: bool,
    default_alpha: float,
) -> tuple[float, dict]:
    """
    Pick Ridge alpha on the latest train year (walk-forward style, no test leakage).
    """
    years = sorted(train_df["year"].unique())
    if len(years) < 4:
        return default_alpha, {
            "alpha_tuning_year": None,
            "alpha_candidates": [],
            "alpha_selected": float(default_alpha),
            "alpha_tuning_mae": None,
        }

    val_year = years[-1]
    fold_train = train_df[train_df["year"] < val_year]
    fold_val = train_df[train_df["year"] == val_year]
    if fold_train["year"].nunique() < 3 or fold_train.empty or fold_val.empty:
        return default_alpha, {
            "alpha_tuning_year": int(val_year),
            "alpha_candidates": [],
            "alpha_selected": float(default_alpha),
            "alpha_tuning_mae": None,
        }

    alpha_grid = (
        [1.0, 5.0, 10.0, 20.0, 50.0, 100.0, 200.0]
        if minimal_for_stable_r2
        else [5.0, 10.0, 20.0, 50.0, 100.0, 200.0, 500.0]
    )

    best_alpha = float(default_alpha)
    best_mae = None
    for alpha in alpha_grid:
        X_train, y_train, _, _ = prepare_xy(
            fold_train,
            use_core_only=use_core_only,
            target=target,
            minimal_for_stable_r2=minimal_for_stable_r2,
        )
        X_val, y_val, _, _ = prepare_xy(
            fold_val,
            use_core_only=use_core_only,
            target=target,
            minimal_for_stable_r2=minimal_for_stable_r2,
        )
        if X_train.empty or X_val.empty or len(X_train) < 10:
            continue

        model = _make_model("ridge", alpha=alpha, max_depth=5)
        model.fit(X_train, y_train)
        val_pred = _clip_vote_shares(model.predict(X_val))
        val_mae = mean_absolute_error(y_val, val_pred)
        if best_mae is None or val_mae < best_mae:
            best_mae = float(val_mae)
            best_alpha = float(alpha)

    return best_alpha, {
        "alpha_tuning_year": int(val_year),
        "alpha_candidates": alpha_grid,
        "alpha_selected": float(best_alpha),
        "alpha_tuning_mae": best_mae,
    }


def _infer_extra_indicator_columns(df_columns: list[str] | None) -> list[str]:
    """Detect extra socio indicator columns dynamically present in the dataset."""
    if not df_columns:
        return []

    reserved = {
        "year",
        "geo_code",
        "dept_code",
        "scope",
        "target",
        "share_winner",
        "election_number",
        "family",
    }
    reserved.update(FAMILIES)
    reserved.update(SOCIO_INDICATORS)
    reserved.update(COMMUNE_GEO_FEATURES)
    reserved.update(ELECTION_CONTEXT_FEATURES)
    reserved.update(["share_winner_prev"])
    reserved.update([f"{fam}_prev" for fam in FAMILIES])
    reserved.update([f"{col}_prev" for col in ELECTION_CONTEXT_FEATURES])

    # Remaining columns from the socio pivot are treated as additional indicators.
    # Exclude columns that already have an explicit lag sibling to avoid leaking
    # same-election outcome/context features.
    return [
        col
        for col in df_columns
        if col not in reserved
        and not col.endswith("_prev")
        and f"{col}_prev" not in df_columns
    ]


def get_feature_columns(
    use_core_only: bool = False,
    target: str | None = None,
    minimal_for_stable_r2: bool = False,
    df_columns: list[str] | None = None,
) -> list[str]:
    """Liste des colonnes utilisÃƒÂ©es comme features (socio + lags + election_number)."""
    if minimal_for_stable_r2 and target:
        # Features minimales : lag de la cible + tendance temps + dÃƒÂ©partement (RÃ‚Â² proche de 0, interprÃƒÂ©table)
        lag_col = TARGET_TO_LAG.get(target)
        base = ([lag_col] if lag_col else ["share_winner_prev"]) + ["election_number"]
        return [c for c in base if c]
    if use_core_only:
        socio = [c for c in CORE_SOCIO if c in SOCIO_INDICATORS]
        lags = [c for c in CORE_LAGS if c]
        commune_geo = [c for c in CORE_COMMUNE_GEO if c]
        return socio + commune_geo + lags + ["election_number"]

    socio = [c for c in SOCIO_INDICATORS if c]
    extra_socio = _infer_extra_indicator_columns(df_columns)
    commune_geo = [c for c in COMMUNE_GEO_FEATURES if c]
    election_context = [c for c in ELECTION_CONTEXT_FEATURES if c]
    lags = ["share_winner_prev"] + [f"{f}_prev" for f in FAMILIES if f]
    election_context_lags = [f"{c}_prev" for c in ELECTION_CONTEXT_FEATURES if c]

    # Preserve order and remove duplicates.
    ordered = (
        socio
        + extra_socio
        + commune_geo
        + election_context
        + lags
        + election_context_lags
        + ["election_number"]
    )
    return list(dict.fromkeys(ordered))


def _build_X_with_dept_dummies(
    df: pd.DataFrame,
    numeric_cols: list[str],
) -> tuple[pd.DataFrame, list[str], pd.DataFrame]:
    """
    Construit la matrice X avec variables numÃƒÂ©riques + indicatrices dÃƒÂ©partement (one-hot, drop_first).
    Conforme au sujet : choix gÃƒÂ©ographique et corrÃƒÂ©lations par territoire.
    """
    df_clean = df.dropna(subset=["target"]).copy()
    for col in numeric_cols:
        if col in df_clean.columns:
            df_clean[col] = pd.to_numeric(df_clean[col], errors="coerce")
    # Remplir NaN des indicateurs socio par la mÃƒÂ©diane (ÃƒÂ©vite biais quand donnÃƒÂ©es manquantes anciennes annÃƒÂ©es)
    for col in numeric_cols:
        if col in df_clean.columns and df_clean[col].isna().any():
            if df_clean[col].notna().any():
                med = df_clean[col].median()
                fill_value = med if pd.notna(med) else 0.0
            else:
                fill_value = 0.0
            df_clean[col] = df_clean[col].fillna(fill_value)
    df_clean = df_clean.fillna(0.0)

    X_num = df_clean[numeric_cols].astype(float)
    out_cols = list(numeric_cols)

    if "dept_code" in df_clean.columns:
        dept_dummies = pd.get_dummies(df_clean["dept_code"].astype(str), prefix="dept", drop_first=True)
        X_num = pd.concat([X_num.reset_index(drop=True), dept_dummies.reset_index(drop=True)], axis=1)
        out_cols = numeric_cols + list(dept_dummies.columns)
    return X_num, out_cols, df_clean


def prepare_xy(
    df: pd.DataFrame,
    use_core_only: bool = False,
    target: str | None = None,
    minimal_for_stable_r2: bool = False,
):
    """
    PrÃƒÂ©pare X (features) et y (target). Inclut indicatrices dÃƒÂ©partement + election_number.
    """
    feature_cols = get_feature_columns(
        use_core_only=use_core_only,
        target=target,
        minimal_for_stable_r2=minimal_for_stable_r2,
        df_columns=list(df.columns),
    )
    available = [c for c in feature_cols if c in df.columns]
    if not available:
        raise ValueError(
            "Aucune feature disponible. Colonnes attendues (au moins une partie): "
            + ", ".join(feature_cols)
        )

    X, all_cols, df_clean = _build_X_with_dept_dummies(df, available)
    y = df_clean["target"].values
    return X, y, all_cols, df_clean


def temporal_split(
    df: pd.DataFrame,
    test_years: list[int] | None = None,
    exclude_first_election_from_train: bool = True,
):
    """
    Split temporel : train = toutes les annÃƒÂ©es sauf les derniÃƒÂ¨res (test).
    Par dÃƒÂ©faut test = 2017 et 2022.
    Si exclude_first_election_from_train=True, la premiÃƒÂ¨re annÃƒÂ©e (ex. 1969) est exclue du train
    pour que les lags correspondent toujours ÃƒÂ  une vraie ÃƒÂ©lection prÃƒÂ©cÃƒÂ©dente.
    """
    if test_years is None:
        test_years = [2017, 2022]
    years = sorted(df["year"].unique())
    base_train_years = [y for y in years if y not in test_years]
    train_years = list(base_train_years)
    if exclude_first_election_from_train and len(years) > 1 and base_train_years:
        first_year = min(years)
        candidate_years = [y for y in base_train_years if y > first_year]
        # Keep at least one train year for short histories (commune: 2012/2017/2022).
        if candidate_years:
            train_years = candidate_years
    train_df = df[df["year"].isin(train_years)]
    test_df = df[df["year"].isin(test_years)]
    return train_df, test_df


def _make_model(model_type: str, alpha: float = 10.0, max_depth: int = 5) -> Pipeline:
    """Pipeline with regularization/complexity controls for small historical datasets."""
    if model_type == "ridge":
        return Pipeline([
            ("scaler", StandardScaler()),
            ("regressor", Ridge(alpha=alpha, random_state=42)),
        ])
    if model_type == "enet":
        return Pipeline([
            ("scaler", StandardScaler()),
            ("regressor", ElasticNet(alpha=0.01, l1_ratio=0.7, max_iter=20000, random_state=42)),
        ])
    if model_type == "rf":
        return Pipeline([
            ("scaler", StandardScaler()),
            ("regressor", RandomForestRegressor(
                n_estimators=300,
                max_depth=max(6, max_depth),
                min_samples_leaf=1,
                random_state=42,
                n_jobs=-1,
            )),
        ])
    if model_type == "et":
        return Pipeline([
            ("scaler", StandardScaler()),
            ("regressor", ExtraTreesRegressor(
                n_estimators=300,
                max_depth=max(8, max_depth),
                min_samples_leaf=1,
                random_state=42,
                n_jobs=-1,
            )),
        ])
    if model_type == "gbr":
        return Pipeline([
            ("scaler", StandardScaler()),
            ("regressor", GradientBoostingRegressor(
                n_estimators=300,
                learning_rate=0.05,
                max_depth=3,
                random_state=42,
            )),
        ])
    if model_type == "hgb":
        return Pipeline([
            ("scaler", StandardScaler()),
            ("regressor", HistGradientBoostingRegressor(
                max_iter=300,
                learning_rate=0.05,
                max_depth=8,
                random_state=42,
            )),
        ])
    raise ValueError(f"Unsupported model_type: {model_type}")

def time_series_cv_metrics(
    df: pd.DataFrame,
    target: str,
    model_type: str = "ridge",
    use_core_only: bool = True,
    test_years_list: list[list[int]] | None = None,
) -> dict:
    """
    Validation croisÃƒÂ©e temporelle : pour chaque bloc d'annÃƒÂ©es de test, on entraÃƒÂ®ne sur le passÃƒÂ©.
    Retourne les mÃƒÂ©triques moyennes (conformÃƒÂ©ment au sujet : dÃƒÂ©coupage en jeux train/test).
    """
    if test_years_list is None:
        test_years_list = [[2007], [2012], [2017], [2022]]
    all_years = sorted(df["year"].unique())
    maes, r2s = [], []
    for test_years in test_years_list:
        # Strict temporal CV: train only on years strictly before the test block.
        first_test_year = min(test_years)
        train_years = [y for y in all_years if y < first_test_year and y > min(all_years)]
        if not train_years or not test_years:
            continue
        train_df = df[df["year"].isin(train_years)]
        test_df = df[df["year"].isin(test_years)]
        X_train, y_train, feature_cols, _ = prepare_xy(
            train_df,
            use_core_only=use_core_only,
            target=target,
        )
        X_test, y_test, _, _ = prepare_xy(
            test_df,
            use_core_only=use_core_only,
            target=target,
        )
        if X_train.empty or X_test.empty or len(X_train) < 10:
            continue
        model = _make_model(model_type, alpha=10.0, max_depth=5)
        model.fit(X_train, y_train)
        y_pred = _clip_vote_shares(model.predict(X_test))
        maes.append(mean_absolute_error(y_test, y_pred))
        r2s.append(r2_score(y_test, y_pred))
    return {
        "cv_mae_mean": float(np.mean(maes)) if maes else None,
        "cv_mae_std": float(np.std(maes)) if maes else None,
        "cv_r2_mean": float(np.mean(r2s)) if r2s else None,
        "cv_r2_std": float(np.std(r2s)) if r2s else None,
        "cv_folds": len(maes),
    }


def train_and_evaluate(
    target: str = "share_winner",
    use_db: bool = True,
    scope: str = "departement",
    test_years: list[int] | None = None,
    min_train_year: int | None = None,
    output_dir: Path | None = None,
    model_type: str = "ridge",
    exclude_first_election_from_train: bool | None = None,
    use_core_only: bool = True,
    run_time_cv: bool = True,
    stable_r2: bool = True,
    safe_predictions: bool = True,
) -> dict:
    """
    Construit le jeu de donnÃƒÂ©es, fait le split temporel, entraÃƒÂ®ne et ÃƒÂ©value.
    Si stable_r2=True : features minimales (lag cible + temps + dept) + forte rÃƒÂ©gularisation pour RÃ‚Â² proche de 0.
    """
    output_dir = output_dir or DEFAULT_OUTPUT_DIR
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if scope not in {"departement", "commune"}:
        raise ValueError(f"Invalid scope: {scope}")
    if exclude_first_election_from_train is None:
        exclude_first_election_from_train = scope != "commune"

    df = build_ml_dataset(target=target, use_db=use_db, include_lags=True, scope=scope)
    train_df, test_df = temporal_split(
        df,
        test_years=test_years,
        exclude_first_election_from_train=exclude_first_election_from_train,
    )
    if min_train_year is not None:
        train_df = train_df[train_df["year"] >= int(min_train_year)].copy()
    if train_df.empty:
        raise RuntimeError(
            "Jeu d'entrainement vide apres split temporel. "
            "Ajustez --test-years ou desactivez l'exclusion de la premiere election."
        )
    if test_df.empty:
        raise RuntimeError(
            "Jeu de test vide pour les annees selectionnees. Verifiez --test-years."
        )

    minimal = stable_r2
    alpha_default = 50.0 if stable_r2 else 10.0
    alpha = alpha_default
    alpha_tuning_info = {}
    if model_type == "ridge":
        alpha, alpha_tuning_info = _select_ridge_alpha_on_latest_history(
            train_df=train_df,
            target=target,
            use_core_only=use_core_only,
            minimal_for_stable_r2=minimal,
            default_alpha=alpha_default,
        )
    X_train, y_train, feature_cols, _ = prepare_xy(
        train_df, use_core_only=use_core_only, target=target, minimal_for_stable_r2=minimal
    )
    X_test, y_test, _, test_clean = prepare_xy(
        test_df, use_core_only=use_core_only, target=target, minimal_for_stable_r2=minimal
    )

    if X_train.empty or X_test.empty:
        raise RuntimeError(
            "Pas assez de donnÃƒÂ©es aprÃƒÂ¨s prÃƒÂ©paration. VÃƒÂ©rifiez que l'ETL a bien chargÃƒÂ© "
            "les rÃƒÂ©sultats et les indicateurs socio-ÃƒÂ©conomiques."
        )

    model = _make_model(model_type, alpha=alpha, max_depth=5)
    model.fit(X_train, y_train)
    y_pred_model_only = _clip_vote_shares(model.predict(X_test))

    baseline_pred = _extract_baseline_predictions(test_clean, target=target)
    baseline_metrics = None
    if baseline_pred is not None:
        baseline_metrics = {
            "baseline_lag_column": get_baseline_lag_column(target),
            "baseline_mae": float(mean_absolute_error(y_test, baseline_pred)),
            "baseline_rmse": float(np.sqrt(mean_squared_error(y_test, baseline_pred))),
            "baseline_r2": float(r2_score(y_test, baseline_pred)),
        }

    selected_prediction_mode = "model"
    validation_compare = {}
    y_pred = y_pred_model_only
    if safe_predictions and baseline_pred is not None:
        validation_compare = _evaluate_model_vs_baseline_on_train(
            train_df=train_df,
            target=target,
            model_type=model_type,
            alpha=alpha,
            max_depth=5,
            use_core_only=use_core_only,
            minimal_for_stable_r2=minimal,
        )
        model_val_mae = validation_compare.get("validation_model_mae_mean")
        baseline_val_mae = validation_compare.get("validation_baseline_mae_mean")
        latest_model_val_mae = validation_compare.get("validation_model_mae_latest")
        latest_baseline_val_mae = validation_compare.get("validation_baseline_mae_latest")
        if (
            model_val_mae is not None
            and baseline_val_mae is not None
            and model_val_mae >= baseline_val_mae
        ):
            # Conservative fallback: keep predictions no worse than the lag baseline on historical validation.
            y_pred = baseline_pred
            selected_prediction_mode = "baseline_fallback"
        elif (
            latest_model_val_mae is not None
            and latest_baseline_val_mae is not None
            and latest_model_val_mae >= latest_baseline_val_mae
        ):
            # Recency guardrail: prefer baseline if model is not better on the latest available fold.
            y_pred = baseline_pred
            selected_prediction_mode = "baseline_fallback_latest"
        elif validation_compare.get("validation_folds", 0) == 0:
            # When no walk-forward fold is possible (short history), prefer the naive lag baseline.
            y_pred = baseline_pred
            selected_prediction_mode = "baseline_fallback_no_cv"

    metrics = {
        "target": target,
        "scope": scope,
        "model_type": model_type,
        "use_core_only": use_core_only,
        "exclude_first_election_from_train": bool(exclude_first_election_from_train),
        "safe_predictions": safe_predictions,
        "selected_prediction_mode": selected_prediction_mode,
        "stable_r2": stable_r2,
        "alpha_default": float(alpha_default),
        "alpha_selected": float(alpha),
        "train_samples": len(X_train),
        "test_samples": len(X_test),
        "test_years": test_years or [2017, 2022],
        "min_train_year": min_train_year,
        "features": feature_cols,
        "mae": float(mean_absolute_error(y_test, y_pred)),
        "rmse": float(np.sqrt(mean_squared_error(y_test, y_pred))),
        "r2": float(r2_score(y_test, y_pred)),
        "model_only_mae": float(mean_absolute_error(y_test, y_pred_model_only)),
        "model_only_rmse": float(np.sqrt(mean_squared_error(y_test, y_pred_model_only))),
        "model_only_r2": float(r2_score(y_test, y_pred_model_only)),
    }
    if baseline_metrics is not None:
        metrics.update(baseline_metrics)
    if validation_compare:
        metrics.update(validation_compare)
    if alpha_tuning_info:
        metrics.update(alpha_tuning_info)

    metrics["reliability_level"] = _reliability_label(
        r2=metrics["r2"],
        mae=metrics["mae"],
        baseline_r2=metrics.get("baseline_r2"),
        baseline_mae=metrics.get("baseline_mae"),
    )

    if run_time_cv:
        cv_metrics = time_series_cv_metrics(
            df, target=target, model_type=model_type, use_core_only=use_core_only and not minimal
        )
        metrics.update(cv_metrics)

    id_cols = ["year"]
    if "geo_code" in test_clean.columns:
        id_cols.append("geo_code")
    if "dept_code" in test_clean.columns:
        id_cols.append("dept_code")
    predictions_df = test_clean[id_cols].copy()
    predictions_df["actual"] = y_test.astype(float)
    predictions_df["pred_model_only"] = y_pred_model_only.astype(float)
    predictions_df["pred_selected"] = y_pred.astype(float)
    predictions_df["selected_prediction_mode"] = selected_prediction_mode
    predictions_df["abs_error_model_only"] = np.abs(
        predictions_df["actual"] - predictions_df["pred_model_only"]
    )
    predictions_df["abs_error_selected"] = np.abs(
        predictions_df["actual"] - predictions_df["pred_selected"]
    )
    if baseline_pred is not None:
        predictions_df["pred_baseline"] = baseline_pred.astype(float)
        predictions_df["abs_error_baseline"] = np.abs(
            predictions_df["actual"] - predictions_df["pred_baseline"]
        )

    sort_cols = [col for col in ["year", "geo_code", "dept_code"] if col in predictions_df.columns]
    predictions_df = predictions_df.sort_values(sort_cols).reset_index(drop=True)
    predictions_path = output_dir / PREDICTIONS_FILENAME
    predictions_df.to_csv(predictions_path, index=False)
    metrics["predictions_file"] = str(predictions_path)

    try:
        import joblib
        joblib.dump(
            {
                "model": model,
                "feature_cols": feature_cols,
                "target": target,
                "safe_predictions": safe_predictions,
                "selected_prediction_mode": selected_prediction_mode,
            },
            output_dir / MODEL_FILENAME,
        )
    except ImportError:
        pass

    with open(output_dir / METRICS_FILENAME, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2, ensure_ascii=False)

    return metrics


def main():
    parser = argparse.ArgumentParser(
        description="Entrainement du modele predictif (part de vote) - elections presidentielles IDF"
    )
    parser.add_argument(
        "--target",
        default="share_winner",
        help="Cible: share_winner (part du gagnant) ou une famille (ex: extreme_droite)",
    )
    parser.add_argument(
        "--scope",
        choices=["departement", "commune"],
        default="departement",
        help="Niveau geographique du modele: departement ou commune",
    )
    parser.add_argument(
        "--no-db",
        action="store_true",
        help="Charger les donnees via l'ETL en memoire au lieu de la base",
    )
    parser.add_argument(
        "--test-years",
        type=str,
        default="2017,2022",
        help="Annees de test separees par des virgules (ex: 2017,2022)",
    )
    parser.add_argument(
        "--min-train-year",
        type=int,
        default=None,
        help="Annee minimale incluse dans l'entrainement (ex: 2012)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=str(DEFAULT_OUTPUT_DIR),
        help="Repertoire de sortie pour le modele et les metriques",
    )
    parser.add_argument(
        "--model",
        choices=["ridge", "enet", "rf", "et", "gbr", "hgb"],
        default="ridge",
        help=(
            "Type de modele: ridge, enet (ElasticNet), rf (Random Forest), "
            "et (ExtraTrees), gbr (Gradient Boosting), hgb (HistGradientBoosting)"
        ),
    )
    parser.add_argument(
        "--core-only",
        action="store_true",
        default=True,
        help="Utiliser uniquement les features noyau (socio cles + lags principaux), defaut True",
    )
    parser.add_argument(
        "--no-core-only",
        action="store_false",
        dest="core_only",
        help="Utiliser toutes les features (socio + tous les lags)",
    )
    parser.add_argument(
        "--no-time-cv",
        action="store_false",
        dest="time_cv",
        default=True,
        help="Desactiver la validation croisee temporelle",
    )
    parser.add_argument(
        "--no-stable-r2",
        action="store_false",
        dest="stable_r2",
        default=True,
        help="Desactiver le mode R2 stabilise (features minimales + forte regularisation)",
    )
    parser.add_argument(
        "--no-safe-predictions",
        action="store_false",
        dest="safe_predictions",
        default=True,
        help="Desactiver le fallback securise vers le baseline lag",
    )
    args = parser.parse_args()

    test_years = [int(y.strip()) for y in args.test_years.split(",") if y.strip()]

    metrics = train_and_evaluate(
        target=args.target,
        use_db=not args.no_db,
        scope=args.scope,
        test_years=test_years,
        min_train_year=args.min_train_year,
        output_dir=Path(args.output_dir),
        model_type=args.model,
        use_core_only=args.core_only,
        run_time_cv=args.time_cv,
        stable_r2=args.stable_r2,
        safe_predictions=args.safe_predictions,
    )

    print("Metriques d'evaluation (split temporel, test=" + str(metrics["test_years"]) + "):")
    print(f"  Scope = {metrics.get('scope')}")
    print(f"  MAE  = {metrics['mae']:.4f}")
    print(f"  RMSE = {metrics['rmse']:.4f}")
    print(f"  R2   = {metrics['r2']:.4f}")
    print(f"  Mode selectionne : {metrics.get('selected_prediction_mode')}")
    print(f"  Fiabilite : {metrics.get('reliability_level')}")
    if metrics.get("baseline_r2") is not None:
        print(
            "  Baseline ("
            + str(metrics.get("baseline_lag_column"))
            + f") -> MAE={metrics['baseline_mae']:.4f}, R2={metrics['baseline_r2']:.4f}"
        )
        print(
            f"  Modele seul -> MAE={metrics['model_only_mae']:.4f}, "
            f"R2={metrics['model_only_r2']:.4f}"
        )
    if metrics.get("cv_r2_mean") is not None:
        print("Validation croisee temporelle (plusieurs annees de test):")
        print(f"  R2 moyen = {metrics['cv_r2_mean']:.4f} (+/- {metrics.get('cv_r2_std', 0):.4f})")
        print(f"  MAE moyen = {metrics['cv_mae_mean']:.4f}")
    print(f"  Modele et metriques enregistres dans: {Path(args.output_dir).resolve()}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())


