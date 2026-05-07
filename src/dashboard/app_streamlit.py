from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.etl.db import get_conn
from src.ml.features import get_family, get_family_from_party_code

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONTAINER_PROJECT_ROOT = Path("/opt/airflow/project")
ML_ARTIFACT_ROOT = PROJECT_ROOT / "data" / "processed" / "ml"


st.set_page_config(
    page_title="MSPR Elections IDF - UX Dashboard",
    page_icon="📊",
    layout="wide",
)


def _inject_style() -> None:
    st.markdown(
        """
        <style>
          @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=Source+Sans+3:wght@400;500;600&display=swap');
          :root { color-scheme: light; }

          .stApp {
            background:
              radial-gradient(circle at 100% 0%, rgba(155, 206, 255, 0.26) 0%, rgba(155, 206, 255, 0.06) 35%, transparent 58%),
              linear-gradient(160deg, #f5f8fc 0%, #eaf1f9 100%);
            color: #10233f;
          }

          .block-container {
            padding-top: 1.15rem;
            padding-bottom: 1.0rem;
          }

          .stApp,
          .stApp p,
          .stApp li,
          .stApp label,
          .stApp h1,
          .stApp h2,
          .stApp h3,
          .stApp h4,
          .stApp h5,
          .stApp h6,
          .stApp [data-testid="stMarkdownContainer"] {
            color: #10233f !important;
            font-family: "Source Sans 3", sans-serif;
          }

          .stApp h1,
          .stApp h2,
          .stApp h3,
          .stApp h4,
          .stApp h5,
          .stApp h6 {
            font-family: "Space Grotesk", sans-serif;
            letter-spacing: 0.01em;
          }

          .stApp [data-testid="stSidebar"] {
            background: #f3f7fe !important;
            border-right: 1px solid #d5dfef;
          }

          .stApp [data-testid="stSidebar"] > div:first-child {
            background: #f3f7fe !important;
          }

          .stApp [data-testid="stSidebar"] * {
            color: #102f57 !important;
          }

          .stApp [data-baseweb="select"] > div {
            background: #ffffff !important;
            border: 1px solid #b9c8e1 !important;
            border-radius: 10px !important;
            box-shadow: none !important;
          }

          .stApp [data-baseweb="popover"] {
            background: #ffffff !important;
            color: #10233f !important;
          }

          .stApp [data-baseweb="tag"] {
            background: #deecff !important;
            border: 1px solid #a8c2e8 !important;
            color: #18457f !important;
            border-radius: 8px !important;
          }

          .stApp [data-testid="stDataFrame"] {
            background: #ffffff !important;
            border: 1px solid #d6e0ef;
            border-radius: 10px;
          }

          .hero-card {
            border: 1px solid #d3dff0;
            border-radius: 16px;
            background: linear-gradient(145deg, #ffffff 0%, #f8fbff 100%);
            padding: 18px 18px 15px 18px;
            box-shadow: 0 8px 20px rgba(14, 42, 78, 0.06);
            margin-bottom: 12px;
          }

          .hero-title {
            margin: 0;
            color: #113463;
            font-size: 1.72rem;
            font-weight: 700;
            line-height: 1.2;
            font-family: "Space Grotesk", sans-serif;
          }

          .hero-text {
            margin: 6px 0 12px 0;
            color: #3e5777;
            font-size: 1rem;
          }

          .hero-tags {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
          }

          .hero-tag {
            border-radius: 999px;
            border: 1px solid #b2c7e8;
            background: #edf4ff;
            color: #1c477c;
            font-size: 0.82rem;
            font-weight: 600;
            padding: 4px 10px;
          }

          .kpi-card {
            border: 1px solid #d6e0ef;
            border-radius: 12px;
            background: #ffffff;
            padding: 14px 16px;
            box-shadow: 0 1px 2px rgba(18, 32, 51, 0.04);
          }

          .kpi-title {
            font-size: 0.85rem;
            color: #5b6576;
            margin-bottom: 4px;
          }

          .kpi-value {
            font-size: 1.6rem;
            color: #143e75;
            font-weight: 700;
          }

          .section-divider {
            margin-top: 8px;
            margin-bottom: 4px;
            color: #49678a;
            font-size: 0.85rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.04em;
          }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_hero(title: str, subtitle: str, tags: list[str]) -> None:
    tags_html = "".join(f"<span class='hero-tag'>{tag}</span>" for tag in tags)
    st.markdown(
        (
            "<section class='hero-card'>"
            f"<h1 class='hero-title'>{title}</h1>"
            f"<p class='hero-text'>{subtitle}</p>"
            f"<div class='hero-tags'>{tags_html}</div>"
            "</section>"
        ),
        unsafe_allow_html=True,
    )


def _query_df(sql: str, params: Iterable | None = None) -> pd.DataFrame:
    conn = get_conn()
    try:
        return pd.read_sql(sql, conn, params=params)
    finally:
        conn.close()


@st.cache_data(ttl=120)
def discover_ml_summary_files() -> list[str]:
    ml_root = PROJECT_ROOT / "data" / "processed" / "ml"
    if not ml_root.exists():
        return []

    candidates: list[Path] = []
    candidates.extend(ml_root.rglob("commune_tuned_summary.csv"))
    candidates.extend(ml_root.rglob("reliable_summary.csv"))
    candidates.extend(ml_root.glob("*_summary.csv"))

    seen: set[str] = set()
    ordered: list[Path] = []
    for path in sorted(candidates, key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True):
        key = str(path.resolve())
        if key in seen:
            continue
        seen.add(key)
        ordered.append(path)

    return [str(p) for p in ordered[:200]]


def _safe_rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT.resolve()))
    except Exception:
        return str(path)


def _is_ml_artifact_root(path: Path) -> bool:
    try:
        return path.resolve() == ML_ARTIFACT_ROOT.resolve()
    except Exception:
        return str(path).replace("\\", "/").rstrip("/") == str(ML_ARTIFACT_ROOT).replace("\\", "/").rstrip("/")


def _normalize_path_text(path_str: str) -> str:
    return str(path_str or "").strip().strip("'").strip('"').replace("\\", "/")


def _normalize_target_key(value: str) -> str:
    return str(value or "").strip().lower().replace(" ", "_").replace("-", "_")


def _style_plotly(fig: go.Figure) -> go.Figure:
    fig.update_layout(
        template="plotly_white",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#ffffff",
        font=dict(color="#172b4d"),
        title_font=dict(color="#0f2f5f"),
        legend=dict(font=dict(color="#172b4d"), title_font=dict(color="#0f2f5f")),
        coloraxis_colorbar=dict(
            tickfont=dict(color="#172b4d"),
            title=dict(font=dict(color="#0f2f5f")),
        ),
        hoverlabel=dict(bgcolor="#ffffff", font_color="#172b4d"),
    )
    fig.update_xaxes(
        gridcolor="#dbe4f2",
        zerolinecolor="#b8c7e0",
        linecolor="#b8c7e0",
        tickfont=dict(color="#172b4d"),
        title_font=dict(color="#0f2f5f"),
    )
    fig.update_yaxes(
        gridcolor="#dbe4f2",
        zerolinecolor="#b8c7e0",
        linecolor="#b8c7e0",
        tickfont=dict(color="#172b4d"),
        title_font=dict(color="#0f2f5f"),
    )
    return fig


@st.cache_data(ttl=120)
def load_ml_summary(summary_path: str) -> pd.DataFrame:
    path = Path(summary_path)
    if not path.exists():
        return pd.DataFrame()

    df = pd.read_csv(path)
    if df.empty:
        return df

    out = df.copy()
    if "r2_mean" in out.columns:
        out["r2"] = pd.to_numeric(out["r2_mean"], errors="coerce")
    else:
        out["r2"] = pd.to_numeric(out.get("r2"), errors="coerce")

    if "mae_mean" in out.columns:
        out["mae"] = pd.to_numeric(out["mae_mean"], errors="coerce")
    else:
        out["mae"] = pd.to_numeric(out.get("mae"), errors="coerce")

    if "rmse_mean" in out.columns:
        out["rmse"] = pd.to_numeric(out["rmse_mean"], errors="coerce")
    else:
        out["rmse"] = pd.to_numeric(out.get("rmse"), errors="coerce")

    if "model" not in out.columns and "model_type" in out.columns:
        out["model"] = out["model_type"]
    if "model" not in out.columns:
        out["model"] = ""

    if "target" not in out.columns:
        if "candidate_id" in out.columns:
            out["target"] = out["candidate_id"]
        else:
            out["target"] = ""

    if "predictions_file" not in out.columns:
        out["predictions_file"] = ""

    out["target"] = out["target"].fillna("").astype(str)
    out["model"] = out["model"].fillna("").astype(str)
    out["predictions_file"] = out["predictions_file"].fillna("").astype(str)

    cols = [c for c in ["target", "model", "r2", "mae", "rmse", "predictions_file"] if c in out.columns]
    out = out[cols].dropna(subset=["r2"]).sort_values("target").reset_index(drop=True)
    return out


def _resolve_predictions_path(summary_path: str, predictions_file: str) -> Path | None:
    normalized = _normalize_path_text(predictions_file)
    if not normalized:
        return None

    pred = Path(normalized)
    if pred.is_absolute() and pred.exists():
        return pred

    container_prefix = str(CONTAINER_PROJECT_ROOT).rstrip("/") + "/"
    if normalized.startswith(container_prefix):
        rel = normalized[len(container_prefix) :]
        candidate = PROJECT_ROOT / rel
        if candidate.exists():
            return candidate

    candidate = PROJECT_ROOT / normalized
    if candidate.exists():
        return candidate

    summary_dir = Path(summary_path).parent
    candidate2 = summary_dir / normalized
    if candidate2.exists():
        return candidate2
    return None


@st.cache_data(ttl=120)
def summary_has_predictions(summary_path: str) -> bool:
    summary_df = load_ml_summary(summary_path)
    if not summary_df.empty:
        candidates = summary_df["predictions_file"].astype(str).str.strip()
        for pred_file in candidates[candidates.ne("")].tolist():
            if _resolve_predictions_path(summary_path, pred_file) is not None:
                return True
    run_root = _infer_run_root(summary_path)
    if run_root == Path(summary_path).parent and _is_ml_artifact_root(run_root):
        return False
    try:
        return any(run_root.rglob("predictions.csv"))
    except Exception:
        return False


def _infer_run_root(summary_path: str) -> Path:
    summary_file = Path(summary_path)
    parent = summary_file.parent
    stem = summary_file.stem
    if stem.endswith("_summary"):
        run_name = stem[: -len("_summary")]
        candidate = parent / run_name
        if candidate.exists() and candidate.is_dir():
            return candidate
    return parent


def _infer_predictions_path(summary_path: str, target: str) -> Path | None:
    run_root = _infer_run_root(summary_path)
    if run_root == Path(summary_path).parent and _is_ml_artifact_root(run_root):
        return None
    target_slug = str(target or "").strip().lower().replace(" ", "_").replace("-", "_")
    if not target_slug:
        return None

    direct = run_root / target_slug / "predictions.csv"
    if direct.exists():
        return direct

    nested = run_root / run_root.name / target_slug / "predictions.csv"
    if nested.exists():
        return nested

    for candidate in run_root.rglob("predictions.csv"):
        parent_slug = candidate.parent.name.strip().lower().replace(" ", "_").replace("-", "_")
        if parent_slug == target_slug:
            return candidate
    return None


@st.cache_data(ttl=120)
def load_predictions_csv(path_str: str) -> pd.DataFrame:
    p = Path(path_str)
    if not p.exists():
        return pd.DataFrame()
    df = pd.read_csv(p)
    if df.empty:
        return df
    for col in ["actual", "pred_selected", "pred_model_only", "pred_baseline"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    if "year" in df.columns:
        df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")
    return df


@st.cache_data(ttl=300)
def load_departments() -> pd.DataFrame:
    sql = """
    SELECT dept_code, dept_name
    FROM geo_department
    WHERE dept_code IN ('75','77','78','91','92','93','94','95')
    ORDER BY dept_code
    """
    return _query_df(sql)


@st.cache_data(ttl=300)
def load_presidential_rows(scope: str) -> pd.DataFrame:
    sql = """
    SELECT
      EXTRACT(YEAR FROM e.election_date)::int AS year,
      e.scope,
      er.insee_code::text AS insee_code,
      LEFT(er.insee_code, 2) AS dept_code,
      gd.dept_name,
      gc.commune_name,
      c.candidate_name,
      c.party_code,
      COALESCE(er.registered, 0)::float AS registered,
      COALESCE(er.votes_cast, 0)::float AS votes_cast,
      COALESCE(er.votes_valid, 0)::float AS votes_valid,
      COALESCE(er.votes, 0)::float AS votes
    FROM election_result er
    JOIN election e ON e.election_id = er.election_id
    JOIN candidate c ON c.candidate_id = er.candidate_id
    LEFT JOIN geo_department gd ON gd.dept_code = LEFT(er.insee_code, 2)
    LEFT JOIN geo_commune gc ON gc.insee_code = er.insee_code
    WHERE e.election_type = 'presidentielle'
      AND e.round = 1
      AND e.scope = %s
      AND LEFT(er.insee_code, 2) IN ('75','77','78','91','92','93','94','95')
    ORDER BY year, dept_code, insee_code, candidate_name
    """
    df = _query_df(sql, (scope,))
    if df.empty:
        return df
    df["year"] = pd.to_numeric(df["year"], errors="coerce").astype(int)
    df["dept_code"] = df["dept_code"].astype(str).str.zfill(2)
    df["insee_code"] = df["insee_code"].astype(str).str.zfill(5)
    df["commune_name"] = df["commune_name"].fillna("").astype(str)
    df["candidate_name"] = df["candidate_name"].astype(str)
    df["party_code"] = df["party_code"].fillna("").astype(str)
    return df


@st.cache_data(ttl=300)
def load_actual_target_trend(scope: str = "commune") -> pd.DataFrame:
    df = load_presidential_rows(scope)
    if df.empty:
        return pd.DataFrame(columns=["year", "target", "actual_db"])

    scoped = df.copy()
    scoped["target"] = scoped.apply(
        lambda row: _family_from_row(str(row["candidate_name"]), str(row["party_code"])),
        axis=1,
    )
    scoped["target"] = scoped["target"].astype(str).map(_normalize_target_key)

    totals = _geo_level_totals(scoped).groupby("year", as_index=False)["votes_valid"].sum()
    by_target = scoped.groupby(["year", "target"], as_index=False)["votes"].sum()
    out = by_target.merge(totals, on="year", how="left")
    out = out[out["votes_valid"] > 0].copy()
    out["actual_db"] = out["votes"] / out["votes_valid"]
    return out[["year", "target", "actual_db"]].sort_values(["target", "year"]).reset_index(drop=True)


@st.cache_data(ttl=300)
def load_indicators() -> pd.DataFrame:
    sql = """
    SELECT indicator_code, indicator_name
    FROM indicator
    ORDER BY indicator_code
    """
    return _query_df(sql)


@st.cache_data(ttl=300)
def load_indicator_values(indicator_code: str) -> pd.DataFrame:
    sql = """
    SELECT
      iv.year::int AS year,
      LEFT(iv.insee_code, 2) AS dept_code,
      gd.dept_name,
      iv.value::float AS value
    FROM indicator_value iv
    JOIN indicator i ON i.indicator_id = iv.indicator_id
    LEFT JOIN geo_department gd ON gd.dept_code = LEFT(iv.insee_code, 2)
    WHERE i.indicator_code = %s
      AND iv.insee_code LIKE '__000'
      AND LEFT(iv.insee_code, 2) IN ('75','77','78','91','92','93','94','95')
    ORDER BY iv.year, dept_code
    """
    return _query_df(sql, (indicator_code,))


def _family_from_row(candidate_name: str, party_code: str) -> str:
    family = get_family(candidate_name)
    if family and family != "autre":
        return family
    fallback = get_family_from_party_code(party_code)
    return fallback if fallback else "autre"


def _geo_level_totals(df: pd.DataFrame) -> pd.DataFrame:
    geo = (
        df.groupby(["year", "dept_code", "insee_code"], as_index=False)
        .agg(
            dept_name=("dept_name", "first"),
            commune_name=("commune_name", "first"),
            registered=("registered", "max"),
            votes_cast=("votes_cast", "max"),
            votes_valid=("votes_valid", "max"),
        )
    )
    return geo


def render_kpis(df: pd.DataFrame) -> None:
    geo = _geo_level_totals(df)
    years = sorted(df["year"].unique().tolist())
    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(
        f"<div class='kpi-card'><div class='kpi-title'>Annees chargees</div><div class='kpi-value'>{len(years)}</div></div>",
        unsafe_allow_html=True,
    )
    c2.markdown(
        f"<div class='kpi-card'><div class='kpi-title'>Lignes election_result</div><div class='kpi-value'>{len(df):,}</div></div>",
        unsafe_allow_html=True,
    )
    c3.markdown(
        f"<div class='kpi-card'><div class='kpi-title'>Territoires (scope)</div><div class='kpi-value'>{geo['insee_code'].nunique():,}</div></div>",
        unsafe_allow_html=True,
    )
    latest_year = max(years) if years else None
    turnout = (
        (geo[geo["year"] == latest_year]["votes_cast"].sum() / geo[geo["year"] == latest_year]["registered"].sum()) * 100.0
        if latest_year is not None and geo[geo["year"] == latest_year]["registered"].sum() > 0
        else 0.0
    )
    c4.markdown(
        "<div class='kpi-card'><div class='kpi-title'>Participation IDF (derniere annee)</div>"
        f"<div class='kpi-value'>{turnout:.1f}%</div></div>",
        unsafe_allow_html=True,
    )


def render_turnout_chart(
    df: pd.DataFrame,
    selected_depts: list[str],
    scope: str,
) -> None:
    geo = _geo_level_totals(df)
    geo = geo[geo["dept_code"].isin(selected_depts)].copy()
    if geo.empty:
        st.warning("Aucune donnee de participation pour la selection.")
        return

    if scope == "commune":
        agg = geo[geo["registered"] > 0].copy()
        agg["turnout_pct"] = (agg["votes_cast"] / agg["registered"]) * 100.0
        agg["commune_label"] = (
            agg["insee_code"]
            + " - "
            + agg["commune_name"].replace("", "Commune inconnue")
        )

        n_communes = agg["commune_label"].nunique()
        if n_communes > 40:
            latest_year = int(agg["year"].max())
            top_communes = (
                agg[agg["year"] == latest_year]
                .sort_values("registered", ascending=False)["commune_label"]
                .head(40)
                .tolist()
            )
            agg = agg[agg["commune_label"].isin(top_communes)].copy()
            st.info(
                "Affichage limite aux 40 communes les plus peuplees "
                f"(selection actuelle: {n_communes} communes)."
            )

        fig = px.line(
            agg.sort_values(["commune_label", "year"]),
            x="year",
            y="turnout_pct",
            color="commune_label",
            markers=True,
            title="Participation au 1er tour presidentiel par commune",
            labels={"year": "Annee", "turnout_pct": "Participation (%)", "commune_label": "Commune"},
        )
        fig.update_layout(legend_title_text="Commune", margin=dict(l=20, r=20, t=60, b=20))
    else:
        agg = (
            geo.groupby(["year", "dept_code", "dept_name"], as_index=False)
            .agg(registered=("registered", "sum"), votes_cast=("votes_cast", "sum"))
        )
        agg = agg[agg["registered"] > 0].copy()
        agg["turnout_pct"] = (agg["votes_cast"] / agg["registered"]) * 100.0
        agg["dept_label"] = agg["dept_code"] + " - " + agg["dept_name"]

        fig = px.line(
            agg.sort_values(["dept_code", "year"]),
            x="year",
            y="turnout_pct",
            color="dept_label",
            markers=True,
            title="Participation au 1er tour presidentiel par departement",
            labels={"year": "Annee", "turnout_pct": "Participation (%)", "dept_label": "Departement"},
        )
        fig.update_layout(legend_title_text="Departement", margin=dict(l=20, r=20, t=60, b=20))

    _style_plotly(fig)
    st.plotly_chart(fig, use_container_width=True)


def render_candidate_ranking(df: pd.DataFrame, selected_year: int, selected_depts: list[str]) -> None:
    scoped = df[(df["year"] == selected_year) & (df["dept_code"].isin(selected_depts))].copy()
    if scoped.empty:
        st.warning("Aucune donnee candidat pour cette annee.")
        return

    geo = _geo_level_totals(scoped)
    denom = geo["votes_valid"].sum()
    if denom <= 0:
        st.warning("Impossible de calculer les parts de vote (votes_valid = 0).")
        return

    by_candidate = (
        scoped.groupby(["candidate_name", "party_code"], as_index=False)
        .agg(votes=("votes", "sum"))
        .sort_values("votes", ascending=False)
    )
    by_candidate["vote_share_pct"] = (by_candidate["votes"] / denom) * 100.0
    top = by_candidate.head(12).copy()
    top["label"] = top["candidate_name"] + " (" + top["party_code"].replace("", "N/A") + ")"
    top = top.sort_values("vote_share_pct", ascending=True)

    fig = px.bar(
        top,
        x="vote_share_pct",
        y="label",
        orientation="h",
        color="vote_share_pct",
        color_continuous_scale="Blues",
        title=f"Top candidats IDF - {selected_year}",
        labels={"vote_share_pct": "Part de vote (%)", "label": "Candidat"},
    )
    fig.update_layout(showlegend=False, margin=dict(l=20, r=20, t=60, b=20))
    _style_plotly(fig)
    st.plotly_chart(fig, use_container_width=True)


def render_family_trend(df: pd.DataFrame, selected_depts: list[str]) -> None:
    scoped = df[df["dept_code"].isin(selected_depts)].copy()
    if scoped.empty:
        st.warning("Aucune donnee bloc politique pour la selection.")
        return

    scoped["family"] = scoped.apply(
        lambda row: _family_from_row(str(row["candidate_name"]), str(row["party_code"])),
        axis=1,
    )
    geo = _geo_level_totals(scoped)
    denom = geo.groupby("year", as_index=False)["votes_valid"].sum().rename(columns={"votes_valid": "votes_valid_total"})

    fam = (
        scoped.groupby(["year", "family"], as_index=False)
        .agg(votes=("votes", "sum"))
        .merge(denom, on="year", how="left")
    )
    fam = fam[fam["votes_valid_total"] > 0].copy()
    fam["share_pct"] = (fam["votes"] / fam["votes_valid_total"]) * 100.0
    fam = fam.sort_values(["year", "family"])

    fig = px.area(
        fam,
        x="year",
        y="share_pct",
        color="family",
        title="Evolution des blocs politiques (part de vote, IDF)",
        labels={"year": "Annee", "share_pct": "Part de vote (%)", "family": "Bloc"},
    )
    fig.update_layout(margin=dict(l=20, r=20, t=60, b=20))
    _style_plotly(fig)
    st.plotly_chart(fig, use_container_width=True)


def render_indicator_chart(indicator_code: str, indicator_name: str, selected_depts: list[str]) -> None:
    values = load_indicator_values(indicator_code)
    values = values[values["dept_code"].isin(selected_depts)].copy()
    if values.empty:
        st.info("Pas de donnees disponibles pour cet indicateur.")
        return

    values["dept_label"] = values["dept_code"] + " - " + values["dept_name"].fillna("")
    fig = px.line(
        values.sort_values(["dept_code", "year"]),
        x="year",
        y="value",
        color="dept_label",
        markers=True,
        title=f"Indicateur socio-economique: {indicator_name} ({indicator_code})",
        labels={"year": "Annee", "value": "Valeur", "dept_label": "Departement"},
    )
    fig.update_layout(legend_title_text="Departement", margin=dict(l=20, r=20, t=60, b=20))
    _style_plotly(fig)
    st.plotly_chart(fig, use_container_width=True)


def render_ml_summary_kpis(summary_df: pd.DataFrame) -> None:
    if summary_df.empty:
        return
    best_r2 = float(summary_df["r2"].max()) if "r2" in summary_df.columns else 0.0
    mean_r2 = float(summary_df["r2"].mean()) if "r2" in summary_df.columns else 0.0
    strong_targets = int((summary_df["r2"] >= 0.5).sum()) if "r2" in summary_df.columns else 0

    c1, c2, c3 = st.columns(3)
    c1.markdown(
        "<div class='kpi-card'><div class='kpi-title'>Meilleur R2</div>"
        f"<div class='kpi-value'>{best_r2:.3f}</div></div>",
        unsafe_allow_html=True,
    )
    c2.markdown(
        "<div class='kpi-card'><div class='kpi-title'>R2 moyen</div>"
        f"<div class='kpi-value'>{mean_r2:.3f}</div></div>",
        unsafe_allow_html=True,
    )
    c3.markdown(
        "<div class='kpi-card'><div class='kpi-title'>Cibles R2 >= 0.5</div>"
        f"<div class='kpi-value'>{strong_targets}</div></div>",
        unsafe_allow_html=True,
    )


def render_ml_section() -> None:
    st.markdown("<div class='section-divider'>Performance des modeles</div>", unsafe_allow_html=True)
    st.caption("Les runs ML sont lus depuis `data/processed/ml`.")

    refresh_col, info_col = st.columns([1, 3])
    with refresh_col:
        if st.button("Actualiser les runs ML", use_container_width=True):
            discover_ml_summary_files.clear()
            load_ml_summary.clear()
            summary_has_predictions.clear()
            load_predictions_csv.clear()
            st.session_state.pop("ml_run_select", None)
            rerun_fn = getattr(st, "rerun", None) or getattr(st, "experimental_rerun", None)
            if callable(rerun_fn):
                rerun_fn()
    with info_col:
        st.caption("Utilise ce bouton apres un nouvel entrainement pour recharger la liste des runs.")

    summary_paths = discover_ml_summary_files()
    if not summary_paths:
        st.info("Aucun fichier de resume ML detecte dans `data/processed/ml`.")
        return
    st.caption(f"Resumes ML detectes: {len(summary_paths)}")

    run_entries: list[tuple[str, bool]] = [(path, summary_has_predictions(path)) for path in summary_paths]
    labels: list[str] = []
    label_to_path: dict[str, str] = {}
    label_has_predictions: dict[str, bool] = {}
    default_index = 0
    for idx, (path, has_predictions) in enumerate(run_entries):
        tag = "predictions" if has_predictions else "metriques only"
        label = f"{idx+1}. {_safe_rel(Path(path))} [{tag}]"
        labels.append(label)
        label_to_path[label] = path
        label_has_predictions[label] = has_predictions

    st.caption(f"Dernier run detecte: `{_safe_rel(Path(run_entries[0][0]))}`")
    selected_label = st.selectbox("Run ML", labels, index=default_index, key="ml_run_select")
    selected_summary_path = label_to_path[selected_label]
    selected_run_has_predictions = label_has_predictions[selected_label]
    summary_df = load_ml_summary(selected_summary_path)
    if summary_df.empty:
        st.info("Resume ML vide ou non lisible.")
        return

    render_ml_summary_kpis(summary_df)

    c1, c2 = st.columns([1, 1])
    with c1:
        chart_df = summary_df.sort_values("r2", ascending=False).copy()
        fig_r2 = px.bar(
            chart_df,
            x="target",
            y="r2",
            color="r2",
            color_continuous_scale="Blues",
            title="R2 par cible",
            labels={"target": "Cible", "r2": "R2"},
        )
        fig_r2.add_hline(y=0.5, line_dash="dash", line_color="#c0392b", annotation_text="Seuil 0.5")
        fig_r2.update_layout(margin=dict(l=20, r=20, t=60, b=20), showlegend=False)
        _style_plotly(fig_r2)
        st.plotly_chart(fig_r2, use_container_width=True)

    with c2:
        display_df = summary_df.copy()
        for col in ["r2", "mae", "rmse"]:
            if col in display_df.columns:
                display_df[col] = display_df[col].round(4)
        st.dataframe(display_df[["target", "model", "r2", "mae", "rmse"]], use_container_width=True, hide_index=True)

    st.markdown("<div class='section-divider'>Detail des predictions</div>", unsafe_allow_html=True)

    targets = summary_df["target"].dropna().astype(str).tolist()
    if not targets:
        return

    selected_target = st.selectbox("Detail cible (predictions)", targets, index=0)
    selected_row = summary_df[summary_df["target"] == selected_target].head(1)
    if selected_row.empty:
        return

    pred_file = str(selected_row["predictions_file"].iloc[0])
    pred_path = _resolve_predictions_path(selected_summary_path, pred_file)
    if pred_path is None:
        pred_path = _infer_predictions_path(selected_summary_path, selected_target)
    if pred_path is None:
        if selected_run_has_predictions:
            st.info(
                "Le fichier `predictions.csv` n'a pas ete retrouve pour cette cible. "
                "Verifie les artefacts de run ou selectionne un autre run."
            )
        else:
            st.info(
                "Ce run fournit uniquement des metriques agregees (pas de `predictions.csv`). "
                "Selectionne un run `commune_tuned_*` pour afficher reel vs predit."
            )
        return

    pred_df = load_predictions_csv(str(pred_path))
    if pred_df.empty or "actual" not in pred_df.columns or "pred_selected" not in pred_df.columns:
        st.info("Fichier predictions present mais contenu non exploitable.")
        return

    p1, p2 = st.columns(2)
    with p1:
        scatter_df = pred_df.dropna(subset=["actual", "pred_selected"]).copy()
        if scatter_df.empty:
            st.info("Pas de lignes exploitables pour le scatter ML.")
        else:
            fig_scatter = px.scatter(
                scatter_df,
                x="actual",
                y="pred_selected",
                title=f"Reel vs predit - {selected_target}",
                labels={"actual": "Reel", "pred_selected": "Prediction"},
                opacity=0.65,
            )
            min_v = float(min(scatter_df["actual"].min(), scatter_df["pred_selected"].min()))
            max_v = float(max(scatter_df["actual"].max(), scatter_df["pred_selected"].max()))
            fig_scatter.add_trace(
                go.Scatter(
                    x=[min_v, max_v],
                    y=[min_v, max_v],
                    mode="lines",
                    name="Ideal",
                    line=dict(dash="dash", color="#6c7a89"),
                )
            )
            fig_scatter.update_layout(margin=dict(l=20, r=20, t=60, b=20))
            _style_plotly(fig_scatter)
            st.plotly_chart(fig_scatter, use_container_width=True)

    with p2:
        if "year" in pred_df.columns:
            year_df = (
                pred_df.dropna(subset=["year", "actual", "pred_selected"])
                .groupby("year", as_index=False)
                .agg(actual=("actual", "mean"), pred_selected=("pred_selected", "mean"))
                .sort_values("year")
            )
            target_key = _normalize_target_key(selected_target)
            actual_trend_df = load_actual_target_trend("commune")
            actual_trend_df = actual_trend_df[actual_trend_df["target"] == target_key].copy()

            if year_df.empty and actual_trend_df.empty:
                st.info("Pas de serie temporelle exploitable.")
            else:
                fig_year = go.Figure()
                if not actual_trend_df.empty:
                    fig_year.add_trace(
                        go.Scatter(
                            x=actual_trend_df["year"],
                            y=actual_trend_df["actual_db"],
                            mode="lines+markers",
                            name="Reel (base complete)",
                            line=dict(color="#163d73", width=3),
                            marker=dict(size=7),
                        )
                    )

                if not year_df.empty:
                    fig_year.add_trace(
                        go.Scatter(
                            x=year_df["year"],
                            y=year_df["actual"],
                            mode="markers",
                            name="Reel (annees test run)",
                            marker=dict(color="#1f77b4", size=8, symbol="circle-open"),
                        )
                    )
                    fig_year.add_trace(
                        go.Scatter(
                            x=year_df["year"],
                            y=year_df["pred_selected"],
                            mode="lines+markers",
                            name="Predit (run)",
                            line=dict(color="#e67e22", width=3),
                            marker=dict(size=8),
                        )
                    )

                fig_year.update_layout(
                    title=f"Historique reel + predictions du run - {selected_target}",
                    xaxis_title="Annee",
                    yaxis_title="Part de vote",
                )
                fig_year.update_layout(margin=dict(l=20, r=20, t=60, b=20))
                _style_plotly(fig_year)
                st.plotly_chart(fig_year, use_container_width=True)

                n_pred_years = int(year_df["year"].nunique()) if not year_df.empty else 0
                if n_pred_years <= 2 and not year_df.empty:
                    years_list = ", ".join(str(int(y)) for y in sorted(year_df["year"].dropna().unique().tolist()))
                    st.caption(
                        "Le run selectionne ne contient que "
                        f"{n_pred_years} annee(s) de prediction ({years_list}). "
                        "La courbe bleue montre l'historique reel complet pour reference."
                    )
        else:
            st.info("La colonne `year` est absente de ce fichier predictions.")

    st.caption(f"Resume: `{_safe_rel(Path(selected_summary_path))}` | Predictions: `{_safe_rel(pred_path)}`")


def render_data_page() -> None:
    render_hero(
        "Page Donnees",
        "Analyse interactive des resultats electoraux et des indicateurs socio-economiques pour l'Ile-de-France.",
        ["Exploration", "Comparaison territoriale", "Contexte socio"],
    )

    with st.sidebar:
        st.markdown("---")
        st.markdown("### Filtres - Donnees")
        scope = st.selectbox("Niveau geographique (scope election)", ["commune", "departement"], index=0)

        dept_df = load_departments()
        dept_codes = dept_df["dept_code"].astype(str).tolist()
        selected_depts = st.multiselect("Departements IDF", dept_codes, default=dept_codes)
        if not selected_depts:
            st.warning("Selectionne au moins un departement.")
            st.stop()

    try:
        pres = load_presidential_rows(scope)
    except Exception as exc:
        st.error("Connexion base impossible. Verifie Docker/PostgreSQL et les variables DB_*.")
        st.exception(exc)
        st.stop()

    if pres.empty:
        st.warning("Aucune donnee electorale chargee pour ce scope.")
        st.stop()

    years = sorted(pres["year"].unique().tolist())
    default_year = years[-1]
    with st.sidebar:
        selected_year = st.selectbox("Annee (classement candidats)", years, index=len(years) - 1)
        selected_communes: list[str] = []
        if scope == "commune":
            available = (
                pres[pres["dept_code"].isin(selected_depts)][["insee_code", "commune_name"]]
                .drop_duplicates()
                .sort_values(["insee_code"])
                .copy()
            )
            available["label"] = available["insee_code"] + " - " + available["commune_name"].replace("", "Commune inconnue")
            commune_options = available["label"].tolist()
            selected_commune_labels = st.multiselect(
                "Communes (scope commune)",
                options=commune_options,
                default=commune_options,
            )
            selected_communes = [x.split(" - ")[0] for x in selected_commune_labels]

        indicators = load_indicators()
        selected_indicator = ""
        if indicators.empty:
            st.info("Aucun indicateur socio disponible.")
        else:
            indicator_options = indicators["indicator_code"].astype(str).tolist()
            selected_indicator = st.selectbox("Indicateur socio", indicator_options, index=0)

    pres_filtered = pres[pres["dept_code"].isin(selected_depts)].copy()
    if scope == "commune":
        if not selected_communes:
            st.warning("Selectionne au moins une commune.")
            st.stop()
        pres_filtered = pres_filtered[pres_filtered["insee_code"].isin(selected_communes)].copy()

    render_kpis(pres_filtered)

    c1, c2 = st.columns(2)
    with c1:
        render_turnout_chart(pres_filtered, selected_depts, scope)
    with c2:
        render_candidate_ranking(pres_filtered, selected_year, selected_depts)

    render_family_trend(pres_filtered, selected_depts)

    if selected_indicator:
        indicator_name_row = indicators[indicators["indicator_code"] == selected_indicator]
        indicator_name = (
            str(indicator_name_row["indicator_name"].iloc[0])
            if not indicator_name_row.empty
            else selected_indicator
        )
        render_indicator_chart(selected_indicator, indicator_name, selected_depts)

    st.caption(
        f"Scope: {scope} | Derniere annee disponible: {default_year} | "
        "Page dediee a la lecture des donnees."
    )


def render_predictions_page() -> None:
    render_hero(
        "Page Predictions",
        "Evaluation des runs ML et visualisation des ecarts entre valeurs reelles et predictions.",
        ["Qualite ML", "R2 par cible", "Reel vs predit"],
    )

    with st.sidebar:
        st.markdown("---")
        st.markdown("### Filtres - Predictions")
        st.caption("Choisis un run puis une cible pour lire les performances et les courbes de prediction.")

    render_ml_section()
    st.caption("Page dediee au pilotage des performances predictives pour la soutenance.")


def main() -> None:
    _inject_style()

    with st.sidebar:
        st.markdown("### Navigation")
        page = st.radio(
            "Page",
            ["Donnees", "Predictions"],
            index=0,
            label_visibility="collapsed",
        )
        st.caption("Navigation UX: deux pages distinctes pour separer analyse de donnees et analyse predictive.")

    if page == "Donnees":
        render_data_page()
    else:
        render_predictions_page()


if __name__ == "__main__":
    main()
