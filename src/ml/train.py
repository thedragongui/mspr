"""
Entraînement du modèle prédictif supervisé : régression de la part de vote (gagnant ou famille).
Split temporel pour éviter le data leakage ; évaluation sur les dernières élections.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import cross_val_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from .data import (
    SOCIO_INDICATORS,
    FAMILIES,
    build_ml_dataset,
)

# Répertoire de sortie des artefacts ML
DEFAULT_OUTPUT_DIR = Path("data/processed/ml")
MODEL_FILENAME = "model.joblib"
METRICS_FILENAME = "metrics.json"


# Sous-ensemble de features "noyau" (sujet: indicateurs fortement corrélés aux résultats)
CORE_SOCIO = ["unemployment_rate", "poverty_rate", "turnout_rate"]
CORE_LAGS = ["share_winner_prev", "extreme_droite_prev", "gauche_prev", "droite_prev"]

# Pour rapprocher le R² de 0 : on privilégie le lag de la cible + peu de features (évite sur-apprentissage)
TARGET_TO_LAG = {
    "share_winner": "share_winner_prev",
    "extreme_droite": "extreme_droite_prev",
    "gauche": "gauche_prev",
    "droite": "droite_prev",
    "centre": "centre_prev",
}


def get_feature_columns(
    use_core_only: bool = False,
    target: str | None = None,
    minimal_for_stable_r2: bool = False,
) -> list[str]:
    """Liste des colonnes utilisées comme features (socio + lags + election_number)."""
    if minimal_for_stable_r2 and target:
        # Features minimales : lag de la cible + tendance temps + département (R² proche de 0, interprétable)
        lag_col = TARGET_TO_LAG.get(target)
        base = ([lag_col] if lag_col else ["share_winner_prev"]) + ["election_number"]
        return [c for c in base if c]
    if use_core_only:
        socio = [c for c in CORE_SOCIO if c in SOCIO_INDICATORS]
        lags = [c for c in CORE_LAGS if c]
        return socio + lags + ["election_number"]
    socio = [c for c in SOCIO_INDICATORS if c]
    lags = ["share_winner_prev"] + [f"{f}_prev" for f in FAMILIES if f]
    return socio + lags + ["election_number"]


def _build_X_with_dept_dummies(df: pd.DataFrame, numeric_cols: list[str]) -> tuple[pd.DataFrame, list[str]]:
    """
    Construit la matrice X avec variables numériques + indicatrices département (one-hot, drop_first).
    Conforme au sujet : choix géographique et corrélations par territoire.
    """
    df_clean = df.dropna(subset=["target"]).copy()
    for col in numeric_cols:
        if col in df_clean.columns:
            df_clean[col] = pd.to_numeric(df_clean[col], errors="coerce")
    # Remplir NaN des indicateurs socio par la médiane (évite biais quand données manquantes anciennes années)
    for col in numeric_cols:
        if col in df_clean.columns and df_clean[col].isna().any():
            med = df_clean[col].median()
            df_clean[col] = df_clean[col].fillna(med if pd.notna(med) else 0.0)
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
    Prépare X (features) et y (target). Inclut indicatrices département + election_number.
    """
    feature_cols = get_feature_columns(
        use_core_only=use_core_only,
        target=target,
        minimal_for_stable_r2=minimal_for_stable_r2,
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
    Split temporel : train = toutes les années sauf les dernières (test).
    Par défaut test = 2017 et 2022.
    Si exclude_first_election_from_train=True, la première année (ex. 1969) est exclue du train
    pour que les lags correspondent toujours à une vraie élection précédente.
    """
    if test_years is None:
        test_years = [2017, 2022]
    years = sorted(df["year"].unique())
    train_years = [y for y in years if y not in test_years]
    if exclude_first_election_from_train and len(years) > 1:
        first_year = min(years)
        train_years = [y for y in train_years if y > first_year]
    train_df = df[df["year"].isin(train_years)]
    test_df = df[df["year"].isin(test_years)]
    return train_df, test_df


def _make_model(model_type: str, alpha: float = 10.0, max_depth: int = 5) -> Pipeline:
    """Pipeline avec régularisation adaptée au petit échantillon (éviter sur-apprentissage)."""
    if model_type == "ridge":
        return Pipeline([
            ("scaler", StandardScaler()),
            ("regressor", Ridge(alpha=alpha, random_state=42)),
        ])
    return Pipeline([
        ("scaler", StandardScaler()),
        ("regressor", RandomForestRegressor(
            n_estimators=80, max_depth=max_depth, min_samples_leaf=2, random_state=42
        )),
    ])


def time_series_cv_metrics(
    df: pd.DataFrame,
    target: str,
    model_type: str = "ridge",
    use_core_only: bool = True,
    test_years_list: list[list[int]] | None = None,
) -> dict:
    """
    Validation croisée temporelle : pour chaque bloc d'années de test, on entraîne sur le passé.
    Retourne les métriques moyennes (conformément au sujet : découpage en jeux train/test).
    """
    if test_years_list is None:
        test_years_list = [[2007], [2012], [2017], [2022]]
    all_years = sorted(df["year"].unique())
    maes, r2s = [], []
    for test_years in test_years_list:
        train_years = [y for y in all_years if y not in test_years and y > min(all_years)]
        if not train_years or not test_years:
            continue
        train_df = df[df["year"].isin(train_years)]
        test_df = df[df["year"].isin(test_years)]
        X_train, y_train, feature_cols, _ = prepare_xy(train_df, use_core_only=use_core_only)
        X_test, y_test, _, _ = prepare_xy(test_df, use_core_only=use_core_only)
        if X_train.empty or X_test.empty or len(X_train) < 10:
            continue
        model = _make_model(model_type, alpha=10.0, max_depth=5)
        model.fit(X_train, y_train)
        y_pred = model.predict(X_test)
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
    test_years: list[int] | None = None,
    output_dir: Path | None = None,
    model_type: str = "ridge",
    exclude_first_election_from_train: bool = True,
    use_core_only: bool = True,
    run_time_cv: bool = True,
    stable_r2: bool = True,
) -> dict:
    """
    Construit le jeu de données, fait le split temporel, entraîne et évalue.
    Si stable_r2=True : features minimales (lag cible + temps + dept) + forte régularisation pour R² proche de 0.
    """
    output_dir = output_dir or DEFAULT_OUTPUT_DIR
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    df = build_ml_dataset(target=target, use_db=use_db, include_lags=True)
    train_df, test_df = temporal_split(
        df,
        test_years=test_years,
        exclude_first_election_from_train=exclude_first_election_from_train,
    )

    minimal = stable_r2
    alpha = 50.0 if stable_r2 else 10.0
    X_train, y_train, feature_cols, _ = prepare_xy(
        train_df, use_core_only=use_core_only, target=target, minimal_for_stable_r2=minimal
    )
    X_test, y_test, _, _ = prepare_xy(
        test_df, use_core_only=use_core_only, target=target, minimal_for_stable_r2=minimal
    )

    if X_train.empty or X_test.empty:
        raise RuntimeError(
            "Pas assez de données après préparation. Vérifiez que l'ETL a bien chargé "
            "les résultats et les indicateurs socio-économiques."
        )

    model = _make_model(model_type, alpha=alpha, max_depth=5)
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)

    metrics = {
        "target": target,
        "model_type": model_type,
        "use_core_only": use_core_only,
        "stable_r2": stable_r2,
        "train_samples": len(X_train),
        "test_samples": len(X_test),
        "test_years": test_years or [2017, 2022],
        "features": feature_cols,
        "mae": float(mean_absolute_error(y_test, y_pred)),
        "rmse": float(np.sqrt(mean_squared_error(y_test, y_pred))),
        "r2": float(r2_score(y_test, y_pred)),
    }

    if run_time_cv:
        cv_metrics = time_series_cv_metrics(
            df, target=target, model_type=model_type, use_core_only=use_core_only and not minimal
        )
        metrics.update(cv_metrics)

    try:
        import joblib
        joblib.dump(
            {"model": model, "feature_cols": feature_cols, "target": target},
            output_dir / MODEL_FILENAME,
        )
    except ImportError:
        pass

    with open(output_dir / METRICS_FILENAME, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2, ensure_ascii=False)

    return metrics


def main():
    parser = argparse.ArgumentParser(
        description="Entraînement du modèle prédictif (part de vote) - élections présidentielles IDF"
    )
    parser.add_argument(
        "--target",
        default="share_winner",
        help="Cible: share_winner (part du gagnant) ou une famille (ex: extreme_droite)",
    )
    parser.add_argument(
        "--no-db",
        action="store_true",
        help="Charger les données via l'ETL en mémoire au lieu de la base",
    )
    parser.add_argument(
        "--test-years",
        type=str,
        default="2017,2022",
        help="Années de test séparées par des virgules (ex: 2017,2022)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=str(DEFAULT_OUTPUT_DIR),
        help="Répertoire de sortie pour le modèle et les métriques",
    )
    parser.add_argument(
        "--model",
        choices=["ridge", "rf"],
        default="ridge",
        help="Type de modèle: ridge (régression Ridge) ou rf (Random Forest)",
    )
    parser.add_argument(
        "--core-only",
        action="store_true",
        default=True,
        help="Utiliser uniquement les features noyau (socio clés + lags principaux), défaut True",
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
        help="Désactiver la validation croisée temporelle",
    )
    parser.add_argument(
        "--no-stable-r2",
        action="store_false",
        dest="stable_r2",
        default=True,
        help="Désactiver le mode R² stabilisé (features minimales + forte régularisation)",
    )
    args = parser.parse_args()

    test_years = [int(y.strip()) for y in args.test_years.split(",") if y.strip()]

    metrics = train_and_evaluate(
        target=args.target,
        use_db=not args.no_db,
        test_years=test_years,
        output_dir=Path(args.output_dir),
        model_type=args.model,
        use_core_only=args.core_only,
        run_time_cv=args.time_cv,
        stable_r2=args.stable_r2,
    )

    print("Métriques d'évaluation (split temporel, test=" + str(metrics["test_years"]) + "):")
    print(f"  MAE  = {metrics['mae']:.4f}")
    print(f"  RMSE = {metrics['rmse']:.4f}")
    print(f"  R²   = {metrics['r2']:.4f}")
    if metrics.get("cv_r2_mean") is not None:
        print("Validation croisée temporelle (plusieurs années de test):")
        print(f"  R² moyen = {metrics['cv_r2_mean']:.4f} (± {metrics.get('cv_r2_std', 0):.4f})")
        print(f"  MAE moyen = {metrics['cv_mae_mean']:.4f}")
    print(f"  Modèle et métriques enregistrés dans: {Path(args.output_dir).resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
