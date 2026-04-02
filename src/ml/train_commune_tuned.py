from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.linear_model import ElasticNet, Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from .data import build_ml_dataset
from .train import temporal_split

DEFAULT_TARGETS = [
    "extreme_gauche",
    "gauche",
    "centre",
    "droite",
    "extreme_droite",
]

TARGET_CONFIG = {
    "extreme_gauche": {
        "model": "ridge",
        "features": None,
    },
    "gauche": {
        "model": "et",
        "features": [
            "gauche_prev",
            "election_number",
            "population_density",
            "centre_prev",
            "droite_nat_prev",
            "left_pressure",
        ],
    },
    "centre": {
        "model": "enet",
        "features": None,
    },
    "droite": {
        "model": "enet_tuned",
        "features": [
            "droite_prev",
            "election_number",
            "population_density",
            "population_log",
            "centre_prev",
            "center_competition",
        ],
    },
    "extreme_droite": {
        "model": "ridge",
        "features": None,
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


def run_tuned_commune_training(
    targets: list[str],
    test_years: list[int],
    min_train_year: int,
    output_dir: Path,
) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_rows: list[dict] = []

    for target in targets:
        if target not in TARGET_CONFIG:
            raise RuntimeError(f"Unsupported target in tuned mode: {target}")

        cfg = TARGET_CONFIG[target]
        df = build_ml_dataset(target=target, use_db=True, include_lags=True, scope="commune")
        train_df, test_df = temporal_split(
            df,
            test_years=test_years,
            exclude_first_election_from_train=False,
        )
        train_df = train_df[train_df["year"] >= int(min_train_year)].copy()

        x_train, y_train, used_features = _prepare_xy(train_df, target, cfg["features"])
        x_test, y_test, _ = _prepare_xy(test_df, target, used_features)
        if x_train.empty or x_test.empty:
            raise RuntimeError(f"Empty design matrix for target={target}")

        model = _make_model(cfg["model"])
        model.fit(x_train, y_train)
        pred = np.clip(model.predict(x_test), 0.0, 1.0)

        target_dir = output_dir / target
        target_dir.mkdir(parents=True, exist_ok=True)

        pred_df = test_df[["year", "geo_code", "dept_code"]].copy()
        pred_df["actual"] = y_test.astype(float)
        pred_df["pred_selected"] = pred.astype(float)
        pred_df["abs_error"] = np.abs(pred_df["actual"] - pred_df["pred_selected"])
        pred_path = target_dir / "predictions.csv"
        pred_df.to_csv(pred_path, index=False)

        metrics = {
            "target": target,
            "scope": "commune",
            "model_type": cfg["model"],
            "test_years": test_years,
            "min_train_year": int(min_train_year),
            "train_samples": int(len(x_train)),
            "test_samples": int(len(x_test)),
            "features": used_features,
            "mae": float(mean_absolute_error(y_test, pred)),
            "rmse": float(np.sqrt(mean_squared_error(y_test, pred))),
            "r2": float(r2_score(y_test, pred)),
            "predictions_file": str(pred_path),
        }
        metrics_path = target_dir / "metrics.json"
        with open(metrics_path, "w", encoding="utf-8") as f:
            json.dump(metrics, f, indent=2, ensure_ascii=False)

        print(
            f"[target={target}] model={cfg['model']} "
            f"R2={metrics['r2']:.4f} MAE={metrics['mae']:.4f} RMSE={metrics['rmse']:.4f}"
        )

        summary_rows.append(
            {
                "target": target,
                "model": cfg["model"],
                "r2": metrics["r2"],
                "mae": metrics["mae"],
                "rmse": metrics["rmse"],
                "train_samples": metrics["train_samples"],
                "test_samples": metrics["test_samples"],
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
        default="2022",
        help="Annees de test separees par virgules",
    )
    parser.add_argument(
        "--min-train-year",
        type=int,
        default=2012,
        help="Annee minimale dans le train (defaut 2012 pour commune)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="data/processed/ml/commune_tuned",
        help="Repertoire de sortie",
    )
    args = parser.parse_args()

    targets = [x.strip() for x in args.targets.split(",") if x.strip()]
    test_years = [int(x.strip()) for x in args.test_years.split(",") if x.strip()]
    run_tuned_commune_training(
        targets=targets,
        test_years=test_years,
        min_train_year=args.min_train_year,
        output_dir=Path(args.output_dir),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
