from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import pandas as pd

from .train import train_and_evaluate

DEFAULT_TARGETS = [
    "extreme_gauche",
    "gauche",
    "centre",
    "droite",
    "extreme_droite",
]

DEFAULT_MODELS = ["ridge", "enet", "rf", "et", "gbr", "hgb"]


def run_benchmark(
    targets: list[str],
    models: list[str],
    test_years: list[int],
    min_train_year: int | None,
    output_dir: Path,
    max_seconds_per_target: int,
    stop_on_positive: bool,
) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    best_by_target: dict[str, dict] = {}

    for target in targets:
        print(f"[target] {target} (scope=commune, test_years={test_years})")
        target_started_at = time.time()
        best = None

        for model in models:
            elapsed = time.time() - target_started_at
            if elapsed >= max_seconds_per_target:
                print(
                    f"  [stop] time budget reached for target={target} "
                    f"({elapsed:.1f}s / {max_seconds_per_target}s)"
                )
                break

            model_output_dir = output_dir / target / model
            metrics = train_and_evaluate(
                target=target,
                use_db=True,
                scope="commune",
                test_years=test_years,
                min_train_year=min_train_year,
                output_dir=model_output_dir,
                model_type=model,
                use_core_only=False,
                run_time_cv=False,
                stable_r2=False,
                safe_predictions=False,
            )

            row = {
                "target": target,
                "model": model,
                "r2": float(metrics.get("r2", float("nan"))),
                "mae": float(metrics.get("mae", float("nan"))),
                "rmse": float(metrics.get("rmse", float("nan"))),
                "train_samples": int(metrics.get("train_samples", 0)),
                "test_samples": int(metrics.get("test_samples", 0)),
                "selected_prediction_mode": str(metrics.get("selected_prediction_mode")),
                "reliability_level": str(metrics.get("reliability_level")),
                "metrics_file": str(model_output_dir / "metrics.json"),
                "predictions_file": str(model_output_dir / "predictions.csv"),
            }
            rows.append(row)

            print(
                f"  [model] {model:<5} r2={row['r2']:.4f} "
                f"mae={row['mae']:.4f} rmse={row['rmse']:.4f}"
            )

            if best is None or row["r2"] > best["r2"]:
                best = row

            if stop_on_positive and row["r2"] > 0:
                print(f"  [stop] positive R2 reached for target={target} with model={model}")
                break

        if best is None:
            best = {
                "target": target,
                "model": None,
                "r2": float("nan"),
                "mae": float("nan"),
                "rmse": float("nan"),
            }
        best_by_target[target] = best
        print(
            f"  [best] target={target} model={best.get('model')} "
            f"r2={best.get('r2', float('nan')):.4f}"
        )

    all_results = pd.DataFrame(rows)
    all_results_path = output_dir / "commune_benchmark_results.csv"
    summary_path = output_dir / "commune_benchmark_best_by_target.json"

    if not all_results.empty:
        all_results = all_results.sort_values(["target", "r2"], ascending=[True, False]).reset_index(
            drop=True
        )
        all_results.to_csv(all_results_path, index=False)

    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(best_by_target, f, indent=2, ensure_ascii=False)

    return {
        "results_csv": str(all_results_path),
        "best_json": str(summary_path),
        "best_by_target": best_by_target,
        "rows": len(rows),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Benchmark rapide des modeles ML sur scope commune, parti par parti."
    )
    parser.add_argument(
        "--targets",
        type=str,
        default=",".join(DEFAULT_TARGETS),
        help="Cibles separees par virgules (ex: gauche,droite,centre)",
    )
    parser.add_argument(
        "--models",
        type=str,
        default=",".join(DEFAULT_MODELS),
        help="Modeles separes par virgules (ridge,enet,rf,et,gbr,hgb)",
    )
    parser.add_argument(
        "--test-years",
        type=str,
        default="2022",
        help="Annees de test separees par virgules (ex: 2017,2022)",
    )
    parser.add_argument(
        "--min-train-year",
        type=int,
        default=2012,
        help="Annee minimale des donnees d'entrainement (defaut 2012 pour scope commune)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="data/processed/ml/bench_commune",
        help="Repertoire de sortie benchmark",
    )
    parser.add_argument(
        "--max-seconds-per-target",
        type=int,
        default=180,
        help="Budget max en secondes par cible",
    )
    parser.add_argument(
        "--stop-on-positive",
        action="store_true",
        help="Arreter un target des qu'un modele atteint un R2 > 0",
    )
    args = parser.parse_args()

    targets = [x.strip() for x in args.targets.split(",") if x.strip()]
    models = [x.strip() for x in args.models.split(",") if x.strip()]
    test_years = [int(x.strip()) for x in args.test_years.split(",") if x.strip()]

    outputs = run_benchmark(
        targets=targets,
        models=models,
        test_years=test_years,
        min_train_year=args.min_train_year,
        output_dir=Path(args.output_dir),
        max_seconds_per_target=args.max_seconds_per_target,
        stop_on_positive=args.stop_on_positive,
    )
    print("[done] benchmark rows=", outputs["rows"])
    print("[done] results_csv=", outputs["results_csv"])
    print("[done] best_json=", outputs["best_json"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
