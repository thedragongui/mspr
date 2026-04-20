from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import PercentFormatter

try:
    from src.etl import run_etl
    from src.ml import train as ml_train
    from src.ml import train_commune_tuned as ml_train_tuned
except ModuleNotFoundError:
    import sys

    sys.path.append(str(Path(__file__).resolve().parents[2]))
    from src.etl import run_etl
    from src.ml import train as ml_train
    from src.ml import train_commune_tuned as ml_train_tuned

OUTPUT_DIR = Path("data/processed/dashboard")
OUTPUT_FILE = OUTPUT_DIR / "idf_dashboard_matplotlib.png"
PREDICTIONS_OUTPUT_FILE = OUTPUT_DIR / "idf_predictions_matplotlib.png"
PREDICTIONS_TUNED_OUTPUT_FILE = OUTPUT_DIR / "idf_predictions_commune_tuned_matplotlib.png"
PREDICTIONS_RELIABLE_OUTPUT_FILE = OUTPUT_DIR / "idf_predictions_reliable_all_years_all_eval_v1_matplotlib.png"
ML_COMPARE_OUTPUT_DIR = Path("data/processed/ml/comparison")
ML_TUNED_OUTPUT_DIR = Path("data/processed/ml/commune_tuned_dashboard")
ML_RELIABLE_OUTPUT_DIR = Path("data/processed/ml/reliable_all_years_all_eval_v1")
PREDICTION_DASHBOARD_TARGETS = [
    "extreme_gauche",
    "gauche",
    "centre",
    "droite",
    "extreme_droite",
]

INDICATOR_LABELS = {
    "unemployment_rate": "Chomage (%)",
    "poverty_rate": "Pauvrete (%)",
}

FIG_BG = "#F4F7FB"
PANEL_BG = "#FFFFFF"
GRID_COLOR = "#D0D7E2"

CORE_COLOR = "#1D4E89"
FULL_COLOR = "#F4A259"
ACTUAL_COLOR = "#2F3C7E"
DIAGONAL_COLOR = "#7A8799"
BAR_BG_COLOR = "#E5EAF1"


def _style_axis(ax, y_is_percent: bool = False):
    ax.set_facecolor(PANEL_BG)
    ax.grid(alpha=0.35, linestyle="--", color=GRID_COLOR)
    ax.set_axisbelow(True)
    if y_is_percent:
        ax.yaxis.set_major_formatter(PercentFormatter(xmax=100, decimals=0))


def _prepare_election_data():
    df = run_etl.collect_election_results_dataframe()
    if df.empty:
        raise RuntimeError("Aucune donnee election disponible pour generer le dashboard.")

    turnout = (
        df[["year", "dept_code", "dept_name", "turnout_rate"]]
        .dropna(subset=["turnout_rate"])
        .drop_duplicates(subset=["year", "dept_code"])
        .copy()
    )
    turnout["turnout_pct"] = turnout["turnout_rate"] * 100

    winner = (
        df.dropna(subset=["vote_share"])
        .sort_values(["year", "dept_code", "vote_share"], ascending=[True, True, False])
        .groupby(["year", "dept_code", "dept_name"], as_index=False)
        .first()
    )
    winner["winner_share_pct"] = winner["vote_share"] * 100

    return turnout, winner


def _prepare_socio_data():
    df = run_etl.collect_socio_indicator_values_dataframe()
    if df.empty:
        raise RuntimeError("Aucune donnee socio-economique disponible pour generer le dashboard.")
    return df


def _plot_turnout(ax, turnout_df, dept_order):
    for code in dept_order:
        chunk = turnout_df[turnout_df["dept_code"] == code].sort_values("year")
        if chunk.empty:
            continue
        ax.plot(
            chunk["year"],
            chunk["turnout_pct"],
            marker="o",
            linewidth=2.0,
            label=f"{code} - {chunk['dept_name'].iloc[0]}",
        )
    ax.set_title("Participation au 1er tour presidentiel (IDF)", fontweight="bold")
    ax.set_xlabel("Annee")
    ax.set_ylabel("Taux de participation (%)")
    _style_axis(ax, y_is_percent=True)


def _plot_winner_heatmap(ax, winner_df, dept_order):
    matrix = (
        winner_df.pivot(index="dept_code", columns="year", values="winner_share_pct")
        .reindex(index=dept_order)
        .sort_index(axis=1)
    )
    img = ax.imshow(matrix.values, aspect="auto", cmap="Blues")
    ax.set_title("Part du candidat arrive 1er (%)", fontweight="bold")
    ax.set_xlabel("Annee")
    ax.set_ylabel("Departement")
    ax.set_xticks(range(len(matrix.columns)))
    ax.set_xticklabels(matrix.columns.astype(int), rotation=45)
    ax.set_yticks(range(len(matrix.index)))
    ax.set_yticklabels(matrix.index.tolist())
    return img


def _plot_socio_timeseries(ax, socio_df, indicator_code, dept_order):
    label = INDICATOR_LABELS.get(indicator_code, indicator_code)
    indicator_df = socio_df[socio_df["indicator_code"] == indicator_code].copy()
    indicator_df["dept_code"] = indicator_df["insee_code"].str[:2]

    for code in dept_order:
        chunk = indicator_df[indicator_df["dept_code"] == code].sort_values("year")
        if chunk.empty:
            continue
        ax.plot(chunk["year"], chunk["value"], marker="o", linewidth=2.0, label=code)

    ax.set_title(f"{label} par departement", fontweight="bold")
    ax.set_xlabel("Annee")
    ax.set_ylabel(label)
    _style_axis(ax)


def _plot_latest_poverty(ax, socio_df, dept_order):
    poverty = socio_df[socio_df["indicator_code"] == "poverty_rate"].copy()
    poverty["dept_code"] = poverty["insee_code"].str[:2]
    if poverty.empty:
        ax.set_title("Pauvrete (%) - donnees indisponibles")
        ax.axis("off")
        return

    latest_year = int(poverty["year"].max())
    latest = poverty[poverty["year"] == latest_year].copy()
    latest = latest.set_index("dept_code").reindex(dept_order).dropna(subset=["value"])

    ax.bar(latest.index, latest["value"], color=CORE_COLOR, edgecolor="#16324F")
    ax.set_title(f"Taux de pauvrete par departement ({latest_year})", fontweight="bold")
    ax.set_xlabel("Departement")
    ax.set_ylabel("Pauvrete (%)")
    _style_axis(ax, y_is_percent=True)


def _run_ml_comparison_predictions(
    target: str = "extreme_droite",
    model_type: str = "rf",
    test_years: tuple[int, ...] = (2017, 2022),
    stable_r2: bool = False,
    safe_predictions: bool = True,
):
    labels_to_core = {"core": True, "full": False}
    prediction_frames = {}
    metrics_by_label = {}

    for label, use_core_only in labels_to_core.items():
        output_dir = ML_COMPARE_OUTPUT_DIR / f"{label}_{target}_{model_type}"
        metrics = ml_train.train_and_evaluate(
            target=target,
            use_db=True,
            test_years=list(test_years),
            output_dir=output_dir,
            model_type=model_type,
            use_core_only=use_core_only,
            run_time_cv=True,
            stable_r2=stable_r2,
            safe_predictions=safe_predictions,
        )
        pred_path = output_dir / ml_train.PREDICTIONS_FILENAME
        if not pred_path.exists():
            raise RuntimeError(f"Prediction file not found: {pred_path}")

        pred_df = pd.read_csv(pred_path)
        pred_df["year"] = pd.to_numeric(pred_df["year"], errors="coerce").astype("Int64")
        pred_df["dept_code"] = pred_df["dept_code"].astype(str).str.zfill(2)
        pred_df["model_scope"] = label
        prediction_frames[label] = pred_df
        metrics_by_label[label] = metrics

    return prediction_frames, metrics_by_label


def _plot_model_only_scatter(ax, core_pred_df, full_pred_df):
    core_actual = core_pred_df["actual"] * 100.0
    core_model = core_pred_df["pred_model_only"] * 100.0
    full_actual = full_pred_df["actual"] * 100.0
    full_model = full_pred_df["pred_model_only"] * 100.0

    ax.scatter(
        core_actual,
        core_model,
        alpha=0.75,
        label="Core (modele seul)",
        color=CORE_COLOR,
        edgecolor="#0D1B2A",
        linewidths=0.35,
    )
    ax.scatter(
        full_actual,
        full_model,
        alpha=0.75,
        label="Full (modele seul)",
        color=FULL_COLOR,
        marker="s",
        edgecolor="#8C4A00",
        linewidths=0.35,
    )

    both_actual = pd.concat([core_actual, full_actual], ignore_index=True)
    both_pred = pd.concat(
        [core_model, full_model],
        ignore_index=True,
    )
    min_edge = float(min(both_actual.min(), both_pred.min()))
    max_edge = float(max(both_actual.max(), both_pred.max()))
    margin = (max_edge - min_edge) * 0.08 if max_edge > min_edge else 2.0
    line_min = min_edge - margin
    line_max = max_edge + margin
    ax.plot(
        [line_min, line_max],
        [line_min, line_max],
        linestyle="--",
        color=DIAGONAL_COLOR,
        linewidth=1.4,
        label="Ligne ideale",
    )

    ax.set_xlim(line_min, line_max)
    ax.set_ylim(line_min, line_max)
    ax.set_title("Reel vs prediction du modele (sans fallback)", fontweight="bold")
    ax.set_xlabel("Part de vote reelle (%)")
    ax.set_ylabel("Part de vote predite (%)")
    _style_axis(ax, y_is_percent=True)
    ax.xaxis.set_major_formatter(PercentFormatter(xmax=100, decimals=0))
    ax.legend(frameon=False, loc="upper left")


def _plot_selected_predictions_by_year(ax, core_pred_df, full_pred_df):
    actual_series = core_pred_df.groupby("year")["actual"].mean().sort_index() * 100.0
    core_series = core_pred_df.groupby("year")["pred_selected"].mean().sort_index() * 100.0
    full_series = full_pred_df.groupby("year")["pred_selected"].mean().sort_index() * 100.0

    ax.plot(
        actual_series.index.astype(int),
        actual_series.values,
        marker="o",
        linewidth=2.4,
        label="Reel (moyenne departements)",
        color=ACTUAL_COLOR,
    )
    ax.plot(
        core_series.index.astype(int),
        core_series.values,
        marker="o",
        linewidth=2.1,
        label="Core (prediction finale)",
        color=CORE_COLOR,
    )
    ax.plot(
        full_series.index.astype(int),
        full_series.values,
        marker="s",
        linewidth=2.1,
        linestyle="--",
        label="Full (prediction finale)",
        color=FULL_COLOR,
    )
    ax.set_title("Prediction finale vs reel (annees de test)", fontweight="bold")
    ax.set_xlabel("Annee")
    ax.set_ylabel("Part de vote (%)")
    _style_axis(ax, y_is_percent=True)
    ax.legend(frameon=False)


def _plot_model_only_mae_by_dept(ax, core_pred_df, full_pred_df):
    core_err = core_pred_df.groupby("dept_code")["abs_error_model_only"].mean() * 100.0
    full_err = full_pred_df.groupby("dept_code")["abs_error_model_only"].mean() * 100.0
    dept_order = sorted(set(core_err.index.tolist()) | set(full_err.index.tolist()))

    core_values = [float(core_err.get(code, np.nan)) for code in dept_order]
    full_values = [float(full_err.get(code, np.nan)) for code in dept_order]

    x = np.arange(len(dept_order))
    width = 0.38
    ax.bar(x - width / 2, core_values, width=width, label="Core", color=CORE_COLOR, edgecolor="#0D1B2A")
    ax.bar(x + width / 2, full_values, width=width, label="Full", color=FULL_COLOR, edgecolor="#8C4A00")

    ax.set_xticks(x)
    ax.set_xticklabels(dept_order)
    ax.set_title("Erreur absolue moyenne (modele seul) par departement", fontweight="bold")
    ax.set_xlabel("Departement")
    ax.set_ylabel("MAE (points de vote)")
    _style_axis(ax)
    ax.legend(frameon=False)


def _plot_ml_summary(ax, metrics_by_label, test_years):
    ax.axis("off")
    ax.set_facecolor(PANEL_BG)
    lines = [
        "Comparaison core vs full",
        f"Annees de test: {list(test_years)}",
        "",
    ]

    for label in ("core", "full"):
        metrics = metrics_by_label[label]
        lines.append(
            f"{label.upper()} final -> R2={metrics.get('r2', float('nan')):.4f}, "
            f"MAE={metrics.get('mae', float('nan')):.4f}, mode={metrics.get('selected_prediction_mode')}"
        )
        lines.append(
            f"{label.upper()} modele seul -> R2={metrics.get('model_only_r2', float('nan')):.4f}, "
            f"MAE={metrics.get('model_only_mae', float('nan')):.4f}"
        )
        lines.append(
            f"{label.upper()} CV -> R2_moy={metrics.get('cv_r2_mean', float('nan')):.4f}, "
            f"MAE_mean={metrics.get('cv_mae_mean', float('nan')):.4f}, "
            f"fiabilite={metrics.get('reliability_level')}"
        )
        lines.append(f"{label.upper()} features={len(metrics.get('features', []))}")
        lines.append("")

    ax.text(
        0.01,
        0.99,
        "\n".join(lines),
        va="top",
        ha="left",
        fontsize=10.5,
        family="monospace",
    )


def build_predictions_dashboard(
    output_path: Path | None = None,
    target: str = "extreme_droite",
    model_type: str = "rf",
    test_years: tuple[int, ...] = (2017, 2022),
    stable_r2: bool = False,
    safe_predictions: bool = True,
):
    if output_path is None:
        if target == "extreme_droite":
            output_path = PREDICTIONS_OUTPUT_FILE
        else:
            output_path = OUTPUT_DIR / f"idf_predictions_{target}_matplotlib.png"

    prediction_frames, metrics_by_label = _run_ml_comparison_predictions(
        target=target,
        model_type=model_type,
        test_years=test_years,
        stable_r2=stable_r2,
        safe_predictions=safe_predictions,
    )
    core_pred_df = prediction_frames["core"]
    full_pred_df = prediction_frames["full"]

    fig, axes = plt.subplots(2, 2, figsize=(18, 11), constrained_layout=True)
    fig.patch.set_facecolor(FIG_BG)
    target_label = target.replace("_", " ").title()
    fig.suptitle(
        f"Predictions vs reel - Core vs Full ({model_type.upper()}, cible: {target_label})",
        fontsize=16,
        fontweight="bold",
    )

    _plot_model_only_scatter(axes[0, 0], core_pred_df, full_pred_df)
    _plot_selected_predictions_by_year(axes[0, 1], core_pred_df, full_pred_df)
    _plot_model_only_mae_by_dept(axes[1, 0], core_pred_df, full_pred_df)
    _plot_ml_summary(axes[1, 1], metrics_by_label, test_years)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=170)
    plt.close(fig)
    return output_path


def build_predictions_dashboards_for_targets(
    targets: list[str] | None = None,
    model_type: str = "rf",
    test_years: tuple[int, ...] = (2017, 2022),
    stable_r2: bool = False,
    safe_predictions: bool = True,
):
    targets = targets or PREDICTION_DASHBOARD_TARGETS
    generated = {}

    for target in targets:
        output_path = build_predictions_dashboard(
            output_path=None,
            target=target,
            model_type=model_type,
            test_years=test_years,
            stable_r2=stable_r2,
            safe_predictions=safe_predictions,
        )
        generated[target] = str(output_path)
    return generated


def build_commune_tuned_predictions_dashboard(
    output_path: Path = PREDICTIONS_TUNED_OUTPUT_FILE,
    targets: list[str] | None = None,
    test_years: tuple[int, ...] | None = None,
    min_train_year: int | None = None,
):
    targets = targets or PREDICTION_DASHBOARD_TARGETS
    run_result = ml_train_tuned.run_tuned_commune_training(
        targets=targets,
        test_years=list(test_years) if test_years else None,
        min_train_year=min_train_year,
        output_dir=ML_TUNED_OUTPUT_DIR,
    )

    summary_df = pd.read_csv(run_result["summary_csv"]).copy()
    summary_df["target_label"] = summary_df["target"].astype(str).str.replace("_", " ").str.title()

    means = []
    for row in summary_df.itertuples(index=False):
        pred_path = Path(row.predictions_file)
        if not pred_path.exists():
            continue
        pred_df = pd.read_csv(pred_path)
        means.append(
            {
                "target": row.target,
                "actual_mean_pct": float(pred_df["actual"].mean() * 100.0),
                "pred_mean_pct": float(pred_df["pred_selected"].mean() * 100.0),
            }
        )
    means_df = pd.DataFrame(means)

    fig, axes = plt.subplots(2, 2, figsize=(18, 11), constrained_layout=True)
    fig.patch.set_facecolor(FIG_BG)
    if test_years:
        test_label = f"test {list(test_years)}"
    else:
        test_label = "test derniere annee disponible"
    fig.suptitle(
        f"Predictions communales tunees (partis principaux, {test_label})",
        fontsize=16,
        fontweight="bold",
    )

    # R2 by target
    ax_r2 = axes[0, 0]
    r2_colors = [CORE_COLOR if r2 > 0 else "#B23A48" for r2 in summary_df["r2"]]
    ax_r2.bar(summary_df["target_label"], summary_df["r2"], color=r2_colors, edgecolor="#1F2937")
    ax_r2.axhline(0.0, color=DIAGONAL_COLOR, linestyle="--", linewidth=1.2)
    ax_r2.set_title("R2 par parti (modele tuned)", fontweight="bold")
    ax_r2.set_xlabel("Parti")
    ax_r2.set_ylabel("R2")
    ax_r2.tick_params(axis="x", rotation=25)
    _style_axis(ax_r2)

    # MAE by target
    ax_mae = axes[0, 1]
    ax_mae.bar(summary_df["target_label"], summary_df["mae"] * 100.0, color=FULL_COLOR, edgecolor="#8C4A00")
    ax_mae.set_title("Erreur absolue moyenne (points de vote)", fontweight="bold")
    ax_mae.set_xlabel("Parti")
    ax_mae.set_ylabel("MAE (points)")
    ax_mae.tick_params(axis="x", rotation=25)
    _style_axis(ax_mae)

    # Actual vs predicted mean by target
    ax_mean = axes[1, 0]
    if not means_df.empty:
        means_df["target_label"] = means_df["target"].astype(str).str.replace("_", " ").str.title()
        x = np.arange(len(means_df))
        w = 0.38
        ax_mean.bar(
            x - w / 2,
            means_df["actual_mean_pct"],
            width=w,
            label="Reel moyen",
            color=ACTUAL_COLOR,
            edgecolor="#0D1B2A",
        )
        ax_mean.bar(
            x + w / 2,
            means_df["pred_mean_pct"],
            width=w,
            label="Prediction moyenne",
            color=CORE_COLOR,
            edgecolor="#16324F",
        )
        ax_mean.set_xticks(x)
        ax_mean.set_xticklabels(means_df["target_label"], rotation=25)
        ax_mean.legend(frameon=False)
    ax_mean.set_title(f"Reel vs prediction moyenne ({test_label})", fontweight="bold")
    ax_mean.set_xlabel("Parti")
    ax_mean.set_ylabel("Part de vote (%)")
    _style_axis(ax_mean, y_is_percent=True)

    # Text summary panel
    ax_txt = axes[1, 1]
    ax_txt.axis("off")
    ax_txt.set_facecolor(PANEL_BG)
    lines = [
        "Mode commune tuned",
        f"Annees test: {list(test_years) if test_years else 'latest'}",
        (
            "Train: toutes annees disponibles"
            if min_train_year is None
            else f"Train >= {int(min_train_year)}"
        ),
        "",
    ]
    for row in summary_df.itertuples(index=False):
        lines.append(
            f"{str(row.target).upper():<15} R2={float(row.r2):.4f}  "
            f"MAE={float(row.mae):.4f}  modele={row.model}"
        )
    lines.append("")
    lines.append(f"Tous les R2 > 0 : {bool((summary_df['r2'] > 0).all())}")
    ax_txt.text(
        0.01,
        0.99,
        "\n".join(lines),
        va="top",
        ha="left",
        fontsize=10.5,
        family="monospace",
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=170)
    plt.close(fig)
    return output_path


def build_reliable_all_years_dashboard(
    output_path: Path = PREDICTIONS_RELIABLE_OUTPUT_FILE,
    input_dir: Path = ML_RELIABLE_OUTPUT_DIR,
):
    summary_path = input_dir / "reliable_summary.csv"
    folds_path = input_dir / "reliable_folds.csv"
    if not summary_path.exists() or not folds_path.exists():
        raise RuntimeError(
            "Resultats reliable_all_years introuvables. "
            f"Attendus: {summary_path} et {folds_path}"
        )

    summary_df = pd.read_csv(summary_path).copy()
    folds_df = pd.read_csv(folds_path).copy()
    if summary_df.empty:
        raise RuntimeError("Le fichier reliable_summary.csv est vide.")

    target_order = [t for t in PREDICTION_DASHBOARD_TARGETS if t in summary_df["target"].astype(str).tolist()]
    if not target_order:
        target_order = sorted(summary_df["target"].astype(str).unique().tolist())
    summary_df["target"] = summary_df["target"].astype(str)
    summary_df["target_label"] = summary_df["target"].str.replace("_", " ").str.title()
    summary_df["target_order"] = summary_df["target"].apply(
        lambda t: target_order.index(t) if t in target_order else 999
    )
    summary_df = summary_df.sort_values("target_order").reset_index(drop=True)

    folds_df["target"] = folds_df["target"].astype(str)
    folds_df["year"] = pd.to_numeric(folds_df["year"], errors="coerce").astype("Int64")

    fig, axes = plt.subplots(2, 2, figsize=(18, 11), constrained_layout=True)
    fig.patch.set_facecolor(FIG_BG)
    fig.suptitle("Fiabilite des predictions (commune, toutes annees)", fontsize=16, fontweight="bold")

    # R2 mean + min by target
    ax_r2 = axes[0, 0]
    x = np.arange(len(summary_df))
    ax_r2.bar(
        x,
        summary_df["r2_mean"],
        color=CORE_COLOR,
        edgecolor="#16324F",
        label="R2 moyen",
    )
    ax_r2.scatter(
        x,
        summary_df["r2_min"],
        color=FULL_COLOR,
        edgecolor="#8C4A00",
        s=80,
        marker="D",
        label="R2 minimum",
    )
    ax_r2.axhline(0.0, color=DIAGONAL_COLOR, linestyle="--", linewidth=1.2)
    ax_r2.set_xticks(x)
    ax_r2.set_xticklabels(summary_df["target_label"], rotation=20)
    ax_r2.set_xlabel("Parti")
    ax_r2.set_ylabel("R2")
    ax_r2.set_title("R2 moyen et minimum par parti", fontweight="bold")
    _style_axis(ax_r2)
    ax_r2.legend(frameon=False)

    # R2 trend by year for each target
    ax_trend = axes[0, 1]
    for target in target_order:
        chunk = folds_df[folds_df["target"] == target].copy()
        if chunk.empty:
            continue
        chunk = chunk.sort_values("year")
        ax_trend.plot(
            chunk["year"].astype(int),
            chunk["r2"],
            marker="o",
            linewidth=2.0,
            label=target.replace("_", " ").title(),
        )
    ax_trend.axhline(0.0, color=DIAGONAL_COLOR, linestyle="--", linewidth=1.2)
    ax_trend.set_title("R2 par annee et par parti", fontweight="bold")
    ax_trend.set_xlabel("Annee de test")
    ax_trend.set_ylabel("R2")
    _style_axis(ax_trend)
    ax_trend.legend(frameon=False, fontsize=9)

    # Error metrics by target
    ax_err = axes[1, 0]
    width = 0.38
    ax_err.bar(
        x - width / 2,
        summary_df["mae_mean"] * 100.0,
        width=width,
        color=FULL_COLOR,
        edgecolor="#8C4A00",
        label="MAE moyenne",
    )
    ax_err.bar(
        x + width / 2,
        summary_df["rmse_mean"] * 100.0,
        width=width,
        color=BAR_BG_COLOR,
        edgecolor="#7A8799",
        label="RMSE moyenne",
    )
    ax_err.set_xticks(x)
    ax_err.set_xticklabels(summary_df["target_label"], rotation=20)
    ax_err.set_xlabel("Parti")
    ax_err.set_ylabel("Erreur (points de vote)")
    ax_err.set_title("Erreurs moyennes par parti", fontweight="bold")
    _style_axis(ax_err)
    ax_err.legend(frameon=False)

    # Text summary
    ax_txt = axes[1, 1]
    ax_txt.axis("off")
    ax_txt.set_facecolor(PANEL_BG)
    lines = [
        f"Source: {input_dir.name}",
        f"Cibles: {len(summary_df)}",
        f"Tous les R2 moyens > 0: {bool((summary_df['r2_mean'] > 0).all())}",
        f"Tous les R2 minimum > 0: {bool((summary_df['r2_min'] > 0).all())}",
        "",
    ]
    for row in summary_df.itertuples(index=False):
        lines.append(
            f"{row.target.upper():<15} R2_mean={float(row.r2_mean):.3f} "
            f"R2_min={float(row.r2_min):.3f} "
            f"MAE={float(row.mae_mean):.3f} "
            f"model={row.model}"
        )
    ax_txt.text(
        0.01,
        0.99,
        "\n".join(lines),
        va="top",
        ha="left",
        fontsize=10.0,
        family="monospace",
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=170)
    plt.close(fig)
    return output_path


def build_dashboard(output_path: Path = OUTPUT_FILE):
    turnout_df, winner_df = _prepare_election_data()
    socio_df = _prepare_socio_data()

    dept_order = sorted(turnout_df["dept_code"].unique().tolist())

    fig, axes = plt.subplots(2, 2, figsize=(18, 11), constrained_layout=True)
    fig.patch.set_facecolor(FIG_BG)
    fig.suptitle(
        "Elections presidentielles IDF - Vue d'ensemble donnees",
        fontsize=16,
        fontweight="bold",
    )

    _plot_turnout(axes[0, 0], turnout_df, dept_order)
    heatmap = _plot_winner_heatmap(axes[0, 1], winner_df, dept_order)
    _plot_socio_timeseries(axes[1, 0], socio_df, "unemployment_rate", dept_order)
    _plot_latest_poverty(axes[1, 1], socio_df, dept_order)

    fig.colorbar(heatmap, ax=axes[0, 1], fraction=0.046, pad=0.04, label="Part (%)")

    handles, labels = axes[0, 0].get_legend_handles_labels()
    if handles:
        fig.legend(handles, labels, loc="lower center", ncols=4, frameon=False)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=170)
    plt.close(fig)
    return output_path


def run_dashboard_pipeline():
    output_path = build_dashboard()
    predictions_outputs = build_predictions_dashboards_for_targets()
    tuned_output = build_commune_tuned_predictions_dashboard()
    reliable_output = build_reliable_all_years_dashboard()
    print(f"[done] dashboard matplotlib donnees genere: {output_path}")
    for target, path in predictions_outputs.items():
        print(f"[done] dashboard matplotlib predictions genere ({target}): {path}")
    print(f"[done] dashboard matplotlib predictions tuned commune genere: {tuned_output}")
    print(f"[done] dashboard matplotlib predictions reliable all-years genere: {reliable_output}")
    return {
        "data_dashboard": str(output_path),
        "predictions_dashboards": predictions_outputs,
        "commune_tuned_dashboard": str(tuned_output),
        "reliable_all_years_dashboard": str(reliable_output),
    }


def main():
    run_dashboard_pipeline()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
