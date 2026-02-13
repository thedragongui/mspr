from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

try:
    from src.etl import run_etl
except ModuleNotFoundError:
    import sys

    sys.path.append(str(Path(__file__).resolve().parents[2]))
    from src.etl import run_etl

OUTPUT_DIR = Path("data/processed/dashboard")
OUTPUT_FILE = OUTPUT_DIR / "idf_dashboard_matplotlib.png"

INDICATOR_LABELS = {
    "unemployment_rate": "Chomage (%)",
    "poverty_rate": "Pauvrete (%)",
}


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
            linewidth=1.8,
            label=f"{code} - {chunk['dept_name'].iloc[0]}",
        )
    ax.set_title("Participation au 1er tour presidentiel")
    ax.set_xlabel("Annee")
    ax.set_ylabel("%")
    ax.grid(alpha=0.25, linestyle="--")


def _plot_winner_heatmap(ax, winner_df, dept_order):
    matrix = (
        winner_df.pivot(index="dept_code", columns="year", values="winner_share_pct")
        .reindex(index=dept_order)
        .sort_index(axis=1)
    )
    img = ax.imshow(matrix.values, aspect="auto", cmap="YlGnBu")
    ax.set_title("Score du candidat arrive 1er (%)")
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
        ax.plot(chunk["year"], chunk["value"], marker="o", linewidth=1.8, label=code)

    ax.set_title(f"{label} par departement")
    ax.set_xlabel("Annee")
    ax.set_ylabel(label)
    ax.grid(alpha=0.25, linestyle="--")


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

    ax.bar(latest.index, latest["value"], color="#2A6F97")
    ax.set_title(f"Pauvrete (%) par departement - {latest_year}")
    ax.set_xlabel("Departement")
    ax.set_ylabel("%")
    ax.grid(axis="y", alpha=0.25, linestyle="--")


def build_dashboard(output_path: Path = OUTPUT_FILE):
    turnout_df, winner_df = _prepare_election_data()
    socio_df = _prepare_socio_data()

    dept_order = sorted(turnout_df["dept_code"].unique().tolist())

    fig, axes = plt.subplots(2, 2, figsize=(18, 11), constrained_layout=True)
    fig.suptitle("Dashboard Matplotlib - Elections Presidentielles IDF (decoupage departemental)")

    _plot_turnout(axes[0, 0], turnout_df, dept_order)
    heatmap = _plot_winner_heatmap(axes[0, 1], winner_df, dept_order)
    _plot_socio_timeseries(axes[1, 0], socio_df, "unemployment_rate", dept_order)
    _plot_latest_poverty(axes[1, 1], socio_df, dept_order)

    fig.colorbar(heatmap, ax=axes[0, 1], fraction=0.046, pad=0.04, label="%")

    handles, labels = axes[0, 0].get_legend_handles_labels()
    if handles:
        fig.legend(handles, labels, loc="lower center", ncols=4, frameon=False)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=170)
    plt.close(fig)
    return output_path


def run_dashboard_pipeline():
    output_path = build_dashboard()
    print(f"[done] dashboard matplotlib genere: {output_path}")
    return str(output_path)


def main():
    run_dashboard_pipeline()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
