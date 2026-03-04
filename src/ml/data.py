"""
Chargement des données pour le ML : résultats électoraux + indicateurs socio-économiques.
Construit un tableau plat (year, département) avec features et cible.
"""
from __future__ import annotations

import os
from pathlib import Path

import pandas as pd

# Import ETL pour fallback sans DB
try:
    from src.etl import run_etl
except ModuleNotFoundError:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from src.etl import run_etl

from .features import get_family

# Années d'élection (1er tour présidentiel)
ELECTION_YEARS = [1969, 1974, 1981, 1988, 1995, 2002, 2007, 2012, 2017, 2022]

# Indicateurs socio-économiques utilisés comme features
SOCIO_INDICATORS = [
    "unemployment_rate",
    "poverty_rate",
    "median_standard_of_living",
    "no_diploma_rate_20_24",
    "social_housing_share",
    "turnout_rate",
]

# Familles politiques pour les features laguées et la cible
FAMILIES = ["extreme_gauche", "gauche", "centre", "droite", "extreme_droite", "droite_nat", "autre"]


def _load_election_results_from_etl() -> pd.DataFrame:
    """Charge les résultats électoraux via l'ETL (sans DB)."""
    df = run_etl.collect_election_results_dataframe()
    if df.empty:
        return df
    df["dept_code"] = df["dept_code"].astype(str).str.zfill(2)
    return df


def _load_socio_from_etl() -> pd.DataFrame:
    """Charge les indicateurs socio-économiques via l'ETL."""
    df = run_etl.collect_socio_indicator_values_dataframe()
    if df.empty:
        return df
    df["dept_code"] = df["insee_code"].astype(str).str[:2]
    return df


def _load_from_db() -> tuple[pd.DataFrame | None, pd.DataFrame | None]:
    """Charge résultats et indicateurs depuis PostgreSQL. Retourne (results_df, socio_df) ou (None, None)."""
    try:
        from src.etl.db import get_conn
        conn = get_conn()
    except Exception:
        return None, None

    try:
        # Résultats: election_result + election + candidate, scope département (insee 75000, 77000...)
        results_sql = """
        SELECT
            EXTRACT(YEAR FROM e.election_date)::int AS year,
            LEFT(er.insee_code, 2) AS dept_code,
            c.candidate_name,
            er.vote_share
        FROM election_result er
        JOIN election e ON e.election_id = er.election_id
        JOIN candidate c ON c.candidate_id = er.candidate_id
        WHERE e.election_type = 'presidentielle'
          AND e.round = 1
          AND e.scope = 'departement'
          AND er.vote_share IS NOT NULL
        ORDER BY year, dept_code, candidate_name
        """
        results_df = pd.read_sql(results_sql, conn)

        # Indicateurs: indicator_value + indicator, insee_code = département (XX000)
        socio_sql = """
        SELECT
            iv.insee_code,
            LEFT(iv.insee_code, 2) AS dept_code,
            iv.year,
            i.indicator_code,
            iv.value
        FROM indicator_value iv
        JOIN indicator i ON i.indicator_id = iv.indicator_id
        WHERE i.indicator_code = ANY(%s)
        """
        with conn.cursor() as cur:
            cur.execute(socio_sql, (SOCIO_INDICATORS,))
            rows = cur.fetchall()
        cols = ["insee_code", "dept_code", "year", "indicator_code", "value"]
        socio_df = pd.DataFrame(rows, columns=cols) if rows else pd.DataFrame(columns=cols)
    except Exception:
        results_df = None
        socio_df = None
    finally:
        conn.close()

    return results_df, socio_df


def load_raw_data(use_db: bool = True) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Charge résultats électoraux et indicateurs socio-économiques.
    use_db=True: tente la base, sinon utilise l'ETL en mémoire.
    Retourne (results_df, socio_df).
    """
    if use_db:
        results_df, socio_df = _load_from_db()
        if results_df is not None and not results_df.empty:
            return results_df, socio_df if socio_df is not None else pd.DataFrame()

    results_df = _load_election_results_from_etl()
    socio_df = _load_socio_from_etl()
    if not socio_df.empty and "indicator_code" not in socio_df.columns:
        # format ETL: indicator_code, insee_code, year, value
        pass  # déjà bon
    return results_df, socio_df


def build_family_shares(results_df: pd.DataFrame) -> pd.DataFrame:
    """
    À partir des résultats par candidat, agrège par (year, dept_code, family)
    et calcule la part du gagnant par (year, dept_code).
    """
    if results_df.empty:
        return pd.DataFrame()

    df = results_df.copy()
    df["family"] = df["candidate_name"].map(get_family)

    # Parts par famille par (year, dept)
    family_shares = (
        df.groupby(["year", "dept_code", "family"], as_index=False)["vote_share"]
        .sum()
        .pivot_table(
            index=["year", "dept_code"],
            columns="family",
            values="vote_share",
            fill_value=0.0,
        )
        .reset_index()
    )

    # Part du gagnant (candidat avec le plus de voix) par (year, dept)
    winner = (
        df.loc[df.groupby(["year", "dept_code"])["vote_share"].idxmax()]
        [["year", "dept_code", "vote_share"]]
        .rename(columns={"vote_share": "share_winner"})
    )
    out = family_shares.merge(winner, on=["year", "dept_code"], how="left")
    return out


def build_socio_pivot(socio_df: pd.DataFrame) -> pd.DataFrame:
    """Pivot indicateurs (indicator_code, year, dept_code) -> une colonne par indicateur."""
    if socio_df.empty:
        return pd.DataFrame(columns=["year", "dept_code"] + SOCIO_INDICATORS)

    pivot = socio_df.copy()
    if "dept_code" not in pivot.columns and "insee_code" in pivot.columns:
        pivot["dept_code"] = pivot["insee_code"].astype(str).str[:2]
    if "indicator_code" not in pivot.columns or "value" not in pivot.columns:
        return pd.DataFrame(columns=["year", "dept_code"] + SOCIO_INDICATORS)
    pivot = pivot.pivot_table(
        index=["year", "dept_code"],
        columns="indicator_code",
        values="value",
        aggfunc="first",
    ).reset_index()
    return pivot


def add_lagged_features(df: pd.DataFrame, family_columns: list[str]) -> pd.DataFrame:
    """
    Ajoute les parts de vote (winner + familles) de l'élection précédente comme features.
    """
    years_sorted = sorted(df["year"].unique())
    if len(years_sorted) < 2:
        return df

    year_to_prev = {
        y: years_sorted[i - 1]
        for i, y in enumerate(years_sorted)
        if i > 0
    }
    df = df.copy()
    df["_prev_year"] = df["year"].map(year_to_prev)

    prev_cols = ["share_winner"] + [c for c in family_columns if c in df.columns]
    prev_df = df[["year", "dept_code"] + prev_cols].copy()
    prev_df = prev_df.rename(columns={
        "year": "_prev_year",
        "share_winner": "share_winner_prev",
        **{c: f"{c}_prev" for c in family_columns if c in prev_df.columns},
    })
    out = df.merge(
        prev_df,
        on=["_prev_year", "dept_code"],
        how="left",
        suffixes=("", "_y"),
    )
    out = out.drop(columns=["_prev_year"], errors="ignore")
    out = out.loc[:, ~out.columns.duplicated()]
    for col in ["share_winner_prev"] + [f"{c}_prev" for c in family_columns]:
        if col in out.columns:
            out[col] = out[col].fillna(0.0)
    return out


def build_ml_dataset(
    target: str = "share_winner",
    use_db: bool = True,
    include_lags: bool = True,
) -> pd.DataFrame:
    """
    Construit le jeu de données ML : une ligne par (year, dept_code).
    - target: 'share_winner' (part du gagnant) ou une famille ex. 'extreme_droite'
    - use_db: charger depuis la base si True, sinon ETL.
    - include_lags: ajouter les parts de l'élection précédente.
    """
    results_df, socio_df = load_raw_data(use_db=use_db)
    if results_df.empty:
        raise RuntimeError("Aucune donnée électorale disponible. Lancez l'ETL : python -m src.etl.run_etl")

    family_shares = build_family_shares(results_df)
    socio_pivot = build_socio_pivot(socio_df)

    # Merge
    df = family_shares.merge(
        socio_pivot,
        on=["year", "dept_code"],
        how="left",
    )

    family_cols = [c for c in FAMILIES if c in df.columns]
    if include_lags:
        df = add_lagged_features(df, family_cols)

    # Numéro d'élection (1 à N) pour capturer la tendance nationale dans le temps (sujet: tendances)
    years_ordered = sorted(df["year"].unique())
    year_to_idx = {y: i + 1 for i, y in enumerate(years_ordered)}
    df["election_number"] = df["year"].map(year_to_idx)

    # Colonne cible pour la régression
    if target == "share_winner":
        df["target"] = df["share_winner"]
    elif target in df.columns:
        df["target"] = df[target]
    else:
        df["target"] = df.get("share_winner", 0.0)

    return df
