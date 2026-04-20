from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

try:
    from src.etl import run_etl
except ModuleNotFoundError:
    import sys

    sys.path.append(str(Path(__file__).resolve().parents[2]))
    from src.etl import run_etl


OUTPUT_DIR = Path("data/processed/dashboard")
OUTPUT_FILE = OUTPUT_DIR / "idf_dashboard_interactive.html"

INDICATOR_LABELS = {
    "unemployment_rate": "Chomage (%)",
    "poverty_rate": "Pauvrete (%)",
    "median_standard_of_living": "Niveau de vie median",
    "social_housing_share": "Part logement social (%)",
}

ML_SUMMARY_CANDIDATES = [
    Path("data/processed/ml/reliable_probe_all_2022_summary.csv"),
    Path("data/processed/ml/commune_tuned_bloc_latest_presentation_v1/commune_tuned_summary.csv"),
    Path("data/processed/ml/commune_tuned/commune_tuned_summary.csv"),
]


def _prepare_election_rows() -> list[dict]:
    results = run_etl.collect_election_results_dataframe()
    if results.empty:
        raise RuntimeError("Aucune donnee election disponible pour le dashboard interactif.")

    turnout = (
        results[["year", "dept_code", "dept_name", "turnout_rate"]]
        .dropna(subset=["turnout_rate"])
        .drop_duplicates(subset=["year", "dept_code"])
        .copy()
    )
    turnout["metric"] = "turnout_pct"
    turnout["value"] = pd.to_numeric(turnout["turnout_rate"], errors="coerce").fillna(0.0) * 100.0
    turnout["winner"] = ""

    winner = (
        results.dropna(subset=["vote_share"])
        .sort_values(["year", "dept_code", "vote_share"], ascending=[True, True, False])
        .groupby(["year", "dept_code", "dept_name"], as_index=False)
        .first()
    )
    winner["metric"] = "winner_share_pct"
    winner["value"] = pd.to_numeric(winner["vote_share"], errors="coerce").fillna(0.0) * 100.0
    winner["winner"] = winner["candidate_name"].astype(str)

    election = pd.concat(
        [
            turnout[["year", "dept_code", "dept_name", "metric", "value", "winner"]],
            winner[["year", "dept_code", "dept_name", "metric", "value", "winner"]],
        ],
        ignore_index=True,
    )
    election["year"] = pd.to_numeric(election["year"], errors="coerce").astype(int)
    election["dept_code"] = election["dept_code"].astype(str).str.zfill(2)
    election["dept_name"] = election["dept_name"].astype(str)

    election = election.sort_values(["metric", "year", "dept_code"]).reset_index(drop=True)
    return election.to_dict(orient="records")


def _prepare_socio_rows() -> tuple[list[dict], dict[str, str]]:
    socio = run_etl.collect_socio_indicator_values_dataframe()
    if socio.empty:
        raise RuntimeError("Aucune donnee socio-economique disponible pour le dashboard interactif.")

    socio = socio.copy()
    socio["insee_code"] = socio["insee_code"].astype(str).str.strip().str.zfill(5)
    socio["dept_code"] = socio["insee_code"].str[:2]

    dept_only = socio[socio["insee_code"].str.endswith("000")].copy()
    if dept_only.empty:
        dept_only = socio.copy()

    wanted = [code for code in INDICATOR_LABELS if code in set(dept_only["indicator_code"].unique())]
    if not wanted:
        wanted = sorted(dept_only["indicator_code"].dropna().astype(str).unique().tolist())[:4]

    filtered = dept_only[dept_only["indicator_code"].isin(wanted)].copy()
    filtered["year"] = pd.to_numeric(filtered["year"], errors="coerce")
    filtered["value"] = pd.to_numeric(filtered["value"], errors="coerce")
    filtered = filtered.dropna(subset=["year", "value"]).copy()
    filtered["year"] = filtered["year"].astype(int)
    filtered = filtered.sort_values(["indicator_code", "dept_code", "year"]).reset_index(drop=True)

    labels = {code: INDICATOR_LABELS.get(code, code) for code in wanted}
    return filtered[["indicator_code", "dept_code", "year", "value"]].to_dict(orient="records"), labels


def _load_ml_summary_rows() -> tuple[list[dict], str]:
    chosen_path = ""
    summary_df: pd.DataFrame | None = None
    for path in ML_SUMMARY_CANDIDATES:
        if path.exists():
            summary_df = pd.read_csv(path)
            chosen_path = str(path)
            break

    if summary_df is None or summary_df.empty:
        return [], "Aucun resume ML trouve."

    df = summary_df.copy()
    if "r2_mean" in df.columns:
        df["r2"] = pd.to_numeric(df["r2_mean"], errors="coerce")
    else:
        df["r2"] = pd.to_numeric(df.get("r2"), errors="coerce")

    if "target" in df.columns:
        target_series = df["target"]
    else:
        target_series = pd.Series([""] * len(df), index=df.index)
    df["target"] = target_series.fillna("").astype(str)

    if "model" in df.columns:
        model_series = df["model"]
    elif "model_type" in df.columns:
        model_series = df["model_type"]
    else:
        model_series = pd.Series([""] * len(df), index=df.index)
    df["model"] = model_series.fillna("").astype(str)

    if "scope" in df.columns:
        scope_series = df["scope"]
    else:
        scope_series = pd.Series(["commune"] * len(df), index=df.index)
    df["scope"] = scope_series.fillna("commune").astype(str)
    df = df.dropna(subset=["r2"]).sort_values("target")

    rows = []
    for _, row in df.iterrows():
        rows.append(
            {
                "target": str(row["target"]),
                "model": str(row["model"]),
                "scope": str(row["scope"]),
                "r2": round(float(row["r2"]), 4),
            }
        )
    return rows, chosen_path


def _build_html(
    election_rows: list[dict],
    socio_rows: list[dict],
    indicator_labels: dict[str, str],
    ml_rows: list[dict],
    ml_source: str,
) -> str:
    election_json = json.dumps(election_rows, ensure_ascii=False)
    socio_json = json.dumps(socio_rows, ensure_ascii=False)
    indicator_json = json.dumps(indicator_labels, ensure_ascii=False)
    ml_json = json.dumps(ml_rows, ensure_ascii=False)

    return f"""<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>MSPR - Dashboard interactif IDF</title>
  <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
  <style>
    :root {{
      --bg: #f6f8fc;
      --card: #ffffff;
      --ink: #122033;
      --muted: #5f6b7a;
      --accent: #1d4e89;
      --accent2: #f4a259;
      --line: #d7deea;
    }}
    body {{
      margin: 0;
      font-family: "Segoe UI", "Arial", sans-serif;
      color: var(--ink);
      background: linear-gradient(150deg, #f6f8fc 0%, #eef3fb 100%);
    }}
    .wrap {{
      max-width: 1200px;
      margin: 0 auto;
      padding: 20px;
      display: grid;
      gap: 16px;
    }}
    .hero {{
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 18px;
    }}
    .hero h1 {{
      margin: 0 0 8px 0;
      font-size: 24px;
      color: var(--accent);
    }}
    .hero p {{
      margin: 0;
      color: var(--muted);
      font-size: 14px;
    }}
    .card {{
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 14px;
    }}
    .controls {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-bottom: 10px;
    }}
    label {{
      font-size: 13px;
      color: var(--muted);
      display: flex;
      gap: 6px;
      align-items: center;
    }}
    select {{
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 5px 8px;
      background: #fff;
      color: var(--ink);
    }}
    #ml-table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 14px;
    }}
    #ml-table th, #ml-table td {{
      padding: 8px;
      border-bottom: 1px solid var(--line);
      text-align: left;
    }}
    #ml-table th {{
      color: var(--muted);
      font-weight: 600;
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <section class="hero">
      <h1>Dashboard interactif - Elections presidentielles IDF</h1>
      <p>Generation automatique depuis l'ETL. Date de generation: {pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")}.</p>
    </section>

    <section class="card">
      <h2>1) Resultats electoraux</h2>
      <div class="controls">
        <label>Annee
          <select id="year-select"></select>
        </label>
        <label>Metrique
          <select id="metric-select">
            <option value="turnout_pct">Taux de participation (%)</option>
            <option value="winner_share_pct">Part du candidat arrive 1er (%)</option>
          </select>
        </label>
      </div>
      <div id="election-chart" style="height: 420px;"></div>
    </section>

    <section class="card">
      <h2>2) Indicateurs socio-economiques</h2>
      <div class="controls">
        <label>Indicateur
          <select id="indicator-select"></select>
        </label>
      </div>
      <div id="socio-chart" style="height: 420px;"></div>
    </section>

    <section class="card">
      <h2>3) Resume ML (R2)</h2>
      <p style="margin-top:0;color:#5f6b7a;">Source: <code>{ml_source or "non disponible"}</code></p>
      <table id="ml-table">
        <thead>
          <tr>
            <th>Cible</th>
            <th>Modele</th>
            <th>Scope</th>
            <th>R2</th>
          </tr>
        </thead>
        <tbody></tbody>
      </table>
    </section>
  </div>

  <script>
    const electionRows = {election_json};
    const socioRows = {socio_json};
    const indicatorLabels = {indicator_json};
    const mlRows = {ml_json};

    const yearSelect = document.getElementById("year-select");
    const metricSelect = document.getElementById("metric-select");
    const indicatorSelect = document.getElementById("indicator-select");

    function initControls() {{
      const years = [...new Set(electionRows.map((row) => row.year))].sort((a, b) => a - b);
      years.forEach((year) => {{
        const option = document.createElement("option");
        option.value = year;
        option.textContent = year;
        yearSelect.appendChild(option);
      }});
      if (years.length) {{
        yearSelect.value = years[years.length - 1];
      }}

      const indicators = Object.keys(indicatorLabels);
      indicators.forEach((code) => {{
        const option = document.createElement("option");
        option.value = code;
        option.textContent = indicatorLabels[code];
        indicatorSelect.appendChild(option);
      }});
      if (indicators.length) {{
        indicatorSelect.value = indicators[0];
      }}
    }}

    function updateElectionChart() {{
      const year = Number(yearSelect.value);
      const metric = metricSelect.value;
      const rows = electionRows
        .filter((row) => row.year === year && row.metric === metric)
        .sort((a, b) => a.dept_code.localeCompare(b.dept_code));

      const labels = rows.map((row) => `${{row.dept_code}} - ${{row.dept_name}}`);
      const values = rows.map((row) => row.value);
      const hover = rows.map((row) => row.winner ? `Vainqueur: ${{row.winner}}` : "");
      const title = metric === "turnout_pct"
        ? `Taux de participation - ${{year}}`
        : `Part du candidat arrive 1er - ${{year}}`;

      Plotly.newPlot(
        "election-chart",
        [{{
          type: "bar",
          x: labels,
          y: values,
          marker: {{ color: metric === "turnout_pct" ? "#1d4e89" : "#f4a259" }},
          hovertemplate: "%{{x}}<br>%{{y:.2f}}%<br>%{{customdata}}<extra></extra>",
          customdata: hover,
        }}],
        {{
          title,
          margin: {{ t: 48, r: 20, b: 90, l: 55 }},
          yaxis: {{ title: "%" }},
          paper_bgcolor: "#ffffff",
          plot_bgcolor: "#ffffff",
        }},
        {{ responsive: true }}
      );
    }}

    function updateSocioChart() {{
      const indicator = indicatorSelect.value;
      const rows = socioRows.filter((row) => row.indicator_code === indicator);
      const deptCodes = [...new Set(rows.map((row) => row.dept_code))].sort((a, b) => a.localeCompare(b));
      const traces = deptCodes.map((dept) => {{
        const series = rows
          .filter((row) => row.dept_code === dept)
          .sort((a, b) => a.year - b.year);
        return {{
          type: "scatter",
          mode: "lines+markers",
          name: dept,
          x: series.map((row) => row.year),
          y: series.map((row) => row.value),
        }};
      }});

      Plotly.newPlot(
        "socio-chart",
        traces,
        {{
          title: indicatorLabels[indicator] || indicator,
          margin: {{ t: 48, r: 20, b: 50, l: 60 }},
          paper_bgcolor: "#ffffff",
          plot_bgcolor: "#ffffff",
        }},
        {{ responsive: true }}
      );
    }}

    function renderMlTable() {{
      const tbody = document.querySelector("#ml-table tbody");
      tbody.innerHTML = "";
      const sorted = [...mlRows].sort((a, b) => a.target.localeCompare(b.target));
      sorted.forEach((row) => {{
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td>${{row.target}}</td>
          <td>${{row.model}}</td>
          <td>${{row.scope}}</td>
          <td>${{Number(row.r2).toFixed(4)}}</td>
        `;
        tbody.appendChild(tr);
      }});
      if (!sorted.length) {{
        const tr = document.createElement("tr");
        tr.innerHTML = '<td colspan="4">Aucune metrique ML trouvee.</td>';
        tbody.appendChild(tr);
      }}
    }}

    initControls();
    updateElectionChart();
    updateSocioChart();
    renderMlTable();
    yearSelect.addEventListener("change", updateElectionChart);
    metricSelect.addEventListener("change", updateElectionChart);
    indicatorSelect.addEventListener("change", updateSocioChart);
  </script>
</body>
</html>
"""


def build_interactive_dashboard(output_path: Path = OUTPUT_FILE) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    election_rows = _prepare_election_rows()
    socio_rows, indicator_labels = _prepare_socio_rows()
    ml_rows, ml_source = _load_ml_summary_rows()

    html = _build_html(
        election_rows=election_rows,
        socio_rows=socio_rows,
        indicator_labels=indicator_labels,
        ml_rows=ml_rows,
        ml_source=ml_source,
    )
    output_path.write_text(html, encoding="utf-8")
    return output_path


def main() -> int:
    path = build_interactive_dashboard()
    print(f"Dashboard interactif genere: {path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
