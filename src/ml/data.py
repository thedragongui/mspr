"""
Data loading for the ML module.
Builds a flat table (year, geo_code) with features and target.
"""
from __future__ import annotations

import io
import os
import re
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

# Import ETL for fallback when DB is unavailable
try:
    from src.etl import run_etl
except ModuleNotFoundError:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from src.etl import run_etl

from .features import get_family, get_family_from_party_code

# First round presidential election years
ELECTION_YEARS = [1969, 1974, 1981, 1988, 1995, 2002, 2007, 2012, 2017, 2022]

DEFAULT_SOCIO_INDICATORS = [
    "unemployment_rate",
    "unemployment_rate_youth_15_24",
    "unemployment_rate_women",
    "unemployment_rate_men",
    "poverty_rate",
    "median_standard_of_living",
    "no_diploma_rate_20_24",
    "social_housing_share",
    "life_expectancy_women",
    "life_expectancy_men",
    "long_term_jobseekers_share",
    "jobseekers_de_count",
    "jobseekers_abc_count",
    "overindebtedness_cases_count",
    "turnout_rate",
]


def _parse_csv_env_list(raw: str) -> list[str]:
    return [item.strip() for item in str(raw or "").split(",") if item.strip()]


EXTRA_SOCIO_INDICATORS = _parse_csv_env_list(os.getenv("ML_EXTRA_SOCIO_INDICATORS", ""))
SOCIO_INDICATORS = list(dict.fromkeys(DEFAULT_SOCIO_INDICATORS + EXTRA_SOCIO_INDICATORS))
USE_ALL_DB_INDICATORS = os.getenv("ML_USE_ALL_DB_INDICATORS", "true").lower() in {
    "1",
    "true",
    "yes",
}

# Political families for lag features and target
FAMILIES = [
    "extreme_gauche",
    "gauche",
    "centre",
    "droite",
    "extreme_droite",
    "droite_nat",
    "divers",
    "autre",
]

# Election fields present in election_result but not fully used in ML previously
ELECTION_CONTEXT_FEATURES = [
    "registered",
    "votes_cast",
    "votes_valid",
    "votes",
    "abstention_rate",
    "valid_ballot_rate",
    "invalid_ballot_rate",
]

COMMUNE_GEO_FEATURES = [
    "population",
    "area_km2",
    "population_density",
    "latitude",
    "longitude",
    "population_log",
]

COMMUNE_TRANSFER_FEATURES = [
    "left_bloc_strength",
    "right_bloc_strength",
    "center_competition",
    "right_pressure",
    "left_pressure",
    "droite_gap_vs_extreme",
    "gauche_gap_vs_extreme",
]

COMMUNE_EXTRA_ODD_FEATURES = [
    "com_social_housing_share",
    "com_hlm_total",
    "com_hlm_occupied",
    "com_hlm_vacant",
    "com_hlm_rented",
    "com_hlm_individuals",
    "com_hlm_students",
    "com_co2_emissions_total",
    "com_co2_netab",
]

COMMUNE_ODD_FEATURE_SPECS = [
    {"feature": "com_social_housing_share", "variable": "part_pls", "sous_champ": ""},
    {"feature": "com_hlm_total", "variable": "log_hlm_tot", "sous_champ": ""},
    {"feature": "com_hlm_occupied", "variable": "log_hlm_phab", "sous_champ": ""},
    {"feature": "com_hlm_vacant", "variable": "nb_vacant_pls", "sous_champ": ""},
    {"feature": "com_hlm_rented", "variable": "nb_dest_loc_pls", "sous_champ": ""},
    {"feature": "com_hlm_individuals", "variable": "nb_ind_pls", "sous_champ": ""},
    {"feature": "com_hlm_students", "variable": "nb_col_etud_pls", "sous_champ": ""},
    {"feature": "com_co2_emissions_total", "variable": "CO2_emissions", "sous_champ": "total"},
    {"feature": "com_co2_netab", "variable": "CO2_netab", "sous_champ": ""},
]

_COMMUNE_ODD_FEATURES_CACHE: pd.DataFrame | None = None


def _load_election_results_from_etl(scope: str = "departement") -> pd.DataFrame:
    """Load election results from ETL (no DB)."""
    if scope == "commune":
        if not hasattr(run_etl, "collect_election_results_commune_dataframe"):
            return pd.DataFrame()
        df = run_etl.collect_election_results_commune_dataframe()
    else:
        df = run_etl.collect_election_results_dataframe()

    if df.empty:
        return df

    df["dept_code"] = df["dept_code"].astype(str).str.zfill(2)
    if "geo_code" not in df.columns:
        if scope == "commune" and "insee_code" in df.columns:
            df["geo_code"] = df["insee_code"].astype(str).str.strip().str.zfill(5)
        else:
            df["geo_code"] = df["dept_code"] + "000"
    return df


def _load_socio_from_etl() -> pd.DataFrame:
    """Load socio-economic indicators from ETL."""
    df = run_etl.collect_socio_indicator_values_dataframe()
    if df.empty:
        return df
    df["dept_code"] = df["insee_code"].astype(str).str[:2]
    return df


def _load_from_db(scope: str = "departement") -> tuple[pd.DataFrame | None, pd.DataFrame | None]:
    """Load election results and indicators from PostgreSQL."""
    try:
        from src.etl.db import get_conn

        conn = get_conn()
    except Exception:
        return None, None

    try:
        if scope not in {"departement", "commune"}:
            raise RuntimeError(f"Invalid scope: {scope}")

        # Presidential first-round results at the selected scope.
        results_sql = """
        SELECT
            EXTRACT(YEAR FROM e.election_date)::int AS year,
            er.insee_code::text AS geo_code,
            LEFT(er.insee_code, 2) AS dept_code,
            c.candidate_name,
            c.party_code,
            er.vote_share,
            er.registered,
            er.votes_cast,
            er.votes_valid,
            er.votes,
            gc.population AS commune_population,
            gc.area_km2 AS commune_area_km2,
            gc.latitude AS commune_latitude,
            gc.longitude AS commune_longitude
        FROM election_result er
        JOIN election e ON e.election_id = er.election_id
        JOIN candidate c ON c.candidate_id = er.candidate_id
        LEFT JOIN geo_commune gc ON gc.insee_code = er.insee_code
        WHERE e.election_type = 'presidentielle'
          AND e.round = 1
          AND e.scope = %s
          AND er.vote_share IS NOT NULL
        ORDER BY year, geo_code, candidate_name
        """
        results_df = pd.read_sql(results_sql, conn, params=(scope,))
        if not results_df.empty:
            results_df["geo_code"] = results_df["geo_code"].astype(str).str.strip()
            results_df["dept_code"] = (
                results_df["dept_code"]
                .astype(str)
                .str.strip()
                .str.zfill(2)
            )
            results_df["insee_code"] = results_df["geo_code"]

        # Indicator values: either all available indicators, or a filtered subset
        socio_sql_base = """
        SELECT
            iv.insee_code,
            LEFT(iv.insee_code, 2) AS dept_code,
            iv.year,
            i.indicator_code,
            iv.value
        FROM indicator_value iv
        JOIN indicator i ON i.indicator_id = iv.indicator_id
        """
        with conn.cursor() as cur:
            if USE_ALL_DB_INDICATORS:
                cur.execute(socio_sql_base)
            else:
                cur.execute(
                    socio_sql_base + " WHERE i.indicator_code = ANY(%s)",
                    (SOCIO_INDICATORS,),
                )
            rows = cur.fetchall()

        cols = ["insee_code", "dept_code", "year", "indicator_code", "value"]
        socio_df = pd.DataFrame(rows, columns=cols) if rows else pd.DataFrame(columns=cols)
    except Exception:
        results_df = None
        socio_df = None
    finally:
        conn.close()

    return results_df, socio_df


def load_raw_data(use_db: bool = True, scope: str = "departement") -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Load election results and socio-economic indicators.
    use_db=True: try PostgreSQL first, then fallback to ETL in-memory extraction.
    """
    if use_db:
        results_df, socio_df = _load_from_db(scope=scope)
        if results_df is not None and not results_df.empty:
            return results_df, socio_df if socio_df is not None else pd.DataFrame()

    results_df = _load_election_results_from_etl(scope=scope)
    socio_df = _load_socio_from_etl()
    return results_df, socio_df


def build_family_shares(results_df: pd.DataFrame) -> pd.DataFrame:
    """
    From candidate-level results, aggregate by (year, dept_code, family)
    and compute winner share by (year, dept_code).
    """
    if results_df.empty:
        return pd.DataFrame()

    df = results_df.copy()
    if "geo_code" not in df.columns:
        if "insee_code" in df.columns:
            df["geo_code"] = df["insee_code"].astype(str).str.strip().str.zfill(5)
        else:
            df["geo_code"] = df["dept_code"].astype(str).str.zfill(2) + "000"

    df["family"] = df["candidate_name"].map(get_family)
    if "party_code" in df.columns:
        missing_mask = df["family"].isna() | (df["family"] == "autre")
        if missing_mask.any():
            df.loc[missing_mask, "family"] = (
                df.loc[missing_mask, "party_code"]
                .map(get_family_from_party_code)
                .fillna(df.loc[missing_mask, "family"])
            )
    df["vote_share"] = pd.to_numeric(df["vote_share"], errors="coerce")
    df_valid = df.dropna(subset=["vote_share"]).copy()
    if df_valid.empty:
        return pd.DataFrame()

    family_shares = (
        df_valid.groupby(["year", "geo_code", "dept_code", "family"], as_index=False)["vote_share"]
        .sum()
        .pivot_table(
            index=["year", "geo_code", "dept_code"],
            columns="family",
            values="vote_share",
            fill_value=0.0,
        )
        .reset_index()
    )

    winner = (
        df_valid.loc[df_valid.groupby(["year", "geo_code"])["vote_share"].idxmax()]
        [["year", "geo_code", "dept_code", "vote_share"]]
        .rename(columns={"vote_share": "share_winner"})
    )
    return family_shares.merge(winner, on=["year", "geo_code", "dept_code"], how="left")


def build_election_context(results_df: pd.DataFrame) -> pd.DataFrame:
    """
    Build additional election context features from existing election_result columns.
    """
    base_cols = ["year", "geo_code", "dept_code"]
    if results_df.empty:
        return pd.DataFrame(columns=base_cols + ELECTION_CONTEXT_FEATURES)

    if "geo_code" not in results_df.columns:
        results_df = results_df.copy()
        if "insee_code" in results_df.columns:
            results_df["geo_code"] = results_df["insee_code"].astype(str).str.strip().str.zfill(5)
        else:
            results_df["geo_code"] = results_df["dept_code"].astype(str).str.zfill(2) + "000"

    available_raw = [c for c in ["registered", "votes_cast", "votes_valid", "votes"] if c in results_df.columns]
    if not available_raw:
        return pd.DataFrame(columns=base_cols + ELECTION_CONTEXT_FEATURES)

    context = (
        results_df[base_cols + available_raw]
        .groupby(base_cols, as_index=False)
        .agg({col: "max" for col in available_raw})
    )

    for col in available_raw:
        context[col] = pd.to_numeric(context[col], errors="coerce")

    if {"registered", "votes_cast"}.issubset(context.columns):
        mask = context["registered"].notna() & (context["registered"] > 0)
        context["abstention_rate"] = np.nan
        context.loc[mask, "abstention_rate"] = (
            1.0 - context.loc[mask, "votes_cast"] / context.loc[mask, "registered"]
        )
        context["abstention_rate"] = context["abstention_rate"].clip(0.0, 1.0)

    if {"votes_cast", "votes_valid"}.issubset(context.columns):
        mask = context["votes_cast"].notna() & (context["votes_cast"] > 0)
        context["valid_ballot_rate"] = np.nan
        context.loc[mask, "valid_ballot_rate"] = (
            context.loc[mask, "votes_valid"] / context.loc[mask, "votes_cast"]
        )
        context["valid_ballot_rate"] = context["valid_ballot_rate"].clip(0.0, 1.0)

        context["invalid_ballot_rate"] = np.nan
        context.loc[mask, "invalid_ballot_rate"] = 1.0 - context.loc[mask, "valid_ballot_rate"]
        context["invalid_ballot_rate"] = context["invalid_ballot_rate"].clip(0.0, 1.0)

    return context


def build_socio_pivot(socio_df: pd.DataFrame) -> pd.DataFrame:
    """Pivot indicators (indicator_code, year, dept_code) to one column per indicator."""
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


def _extract_commune_odd_feature_pivot() -> pd.DataFrame:
    """
    Extract selected commune-level socio features from the cached ODD_COM files.
    This augments department-level indicators with year-varying commune context.
    """
    global _COMMUNE_ODD_FEATURES_CACHE
    if _COMMUNE_ODD_FEATURES_CACHE is not None:
        return _COMMUNE_ODD_FEATURES_CACHE.copy()

    feature_map = {
        f"{spec['variable']}||{spec['sous_champ']}": spec["feature"]
        for spec in COMMUNE_ODD_FEATURE_SPECS
    }
    idf_depts = set(getattr(run_etl, "TARGET_DEPT_CODES", []))
    election_years = set(ELECTION_YEARS)

    try:
        outer_zip = run_etl._cached_download(run_etl.ODD_DEP_ZIP_URL)
    except Exception:
        _COMMUNE_ODD_FEATURES_CACHE = pd.DataFrame(columns=["year", "geo_code"] + COMMUNE_EXTRA_ODD_FEATURES)
        return _COMMUNE_ODD_FEATURES_CACHE.copy()

    records = []
    try:
        with zipfile.ZipFile(outer_zip, "r") as outer:
            nested_bytes = outer.read("ODD_COM.zip")
        with zipfile.ZipFile(io.BytesIO(nested_bytes), "r") as nested:
            for csv_name in nested.namelist():
                with nested.open(csv_name) as raw:
                    for chunk in pd.read_csv(raw, sep=";", encoding="latin-1", chunksize=120000, dtype=str):
                        if "codgeo" not in chunk.columns or "variable" not in chunk.columns:
                            continue

                        chunk["codgeo"] = chunk["codgeo"].astype(str).str.strip()
                        chunk = chunk[chunk["codgeo"].str.len() == 5]
                        chunk = chunk[chunk["codgeo"].str[:2].isin(idf_depts)]
                        if chunk.empty:
                            continue

                        chunk["sous_champ"] = chunk["sous_champ"].fillna("").astype(str).str.strip()
                        chunk["key"] = chunk["variable"].astype(str).str.strip() + "||" + chunk["sous_champ"]
                        chunk = chunk[chunk["key"].isin(feature_map)]
                        if chunk.empty:
                            continue

                        year_cols = [c for c in chunk.columns if re.fullmatch(r"A\d{4}", str(c))]
                        if not year_cols:
                            continue

                        melted = chunk[["codgeo", "key"] + year_cols].melt(
                            id_vars=["codgeo", "key"],
                            value_vars=year_cols,
                            var_name="year_col",
                            value_name="value",
                        )
                        melted["year"] = melted["year_col"].str[1:].astype(int)
                        melted = melted[melted["year"].isin(election_years)]
                        melted["value"] = pd.to_numeric(melted["value"], errors="coerce")
                        melted = melted.dropna(subset=["value"])
                        if melted.empty:
                            continue

                        melted["feature"] = melted["key"].map(feature_map)
                        melted["geo_code"] = melted["codgeo"].astype(str).str.zfill(5)
                        records.append(melted[["year", "geo_code", "feature", "value"]])
    except Exception:
        _COMMUNE_ODD_FEATURES_CACHE = pd.DataFrame(columns=["year", "geo_code"] + COMMUNE_EXTRA_ODD_FEATURES)
        return _COMMUNE_ODD_FEATURES_CACHE.copy()

    if not records:
        _COMMUNE_ODD_FEATURES_CACHE = pd.DataFrame(columns=["year", "geo_code"] + COMMUNE_EXTRA_ODD_FEATURES)
        return _COMMUNE_ODD_FEATURES_CACHE.copy()

    raw_df = pd.concat(records, ignore_index=True)
    pivot = raw_df.pivot_table(
        index=["year", "geo_code"],
        columns="feature",
        values="value",
        aggfunc="first",
    ).reset_index()

    for col in COMMUNE_EXTRA_ODD_FEATURES:
        if col not in pivot.columns:
            pivot[col] = np.nan

    _COMMUNE_ODD_FEATURES_CACHE = pivot
    return _COMMUNE_ODD_FEATURES_CACHE.copy()


def build_commune_geo_features(results_df: pd.DataFrame) -> pd.DataFrame:
    """
    Build commune-level static geographic features from geo_commune-enriched columns.
    """
    base_cols = ["year", "geo_code", "dept_code"]
    source_cols = [
        "commune_population",
        "commune_area_km2",
        "commune_latitude",
        "commune_longitude",
    ]
    if results_df.empty or not any(col in results_df.columns for col in source_cols):
        return pd.DataFrame(columns=base_cols + COMMUNE_GEO_FEATURES)

    df = results_df.copy()
    if "geo_code" not in df.columns:
        if "insee_code" in df.columns:
            df["geo_code"] = df["insee_code"].astype(str).str.strip().str.zfill(5)
        else:
            return pd.DataFrame(columns=base_cols + COMMUNE_GEO_FEATURES)

    available = [col for col in source_cols if col in df.columns]
    out = (
        df[base_cols + available]
        .groupby(base_cols, as_index=False)
        .agg({col: "max" for col in available})
        .rename(
            columns={
                "commune_population": "population",
                "commune_area_km2": "area_km2",
                "commune_latitude": "latitude",
                "commune_longitude": "longitude",
            }
        )
    )

    for col in ["population", "area_km2", "latitude", "longitude"]:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
        else:
            out[col] = np.nan

    valid_area = out["area_km2"].notna() & (out["area_km2"] > 0)
    out["population_density"] = np.nan
    out.loc[valid_area, "population_density"] = (
        out.loc[valid_area, "population"] / out.loc[valid_area, "area_km2"]
    )
    out["population_log"] = np.log1p(out["population"].clip(lower=0))
    return out


def add_lagged_columns(
    df: pd.DataFrame,
    columns_to_lag: list[str],
    fill_value: float = 0.0,
    group_key: str = "geo_code",
) -> pd.DataFrame:
    """
    Add previous-election lag columns for selected features.
    """
    years_sorted = sorted(df["year"].unique())
    if len(years_sorted) < 2:
        return df

    lag_cols = [col for col in columns_to_lag if col in df.columns]
    if not lag_cols:
        return df
    if group_key not in df.columns:
        if "dept_code" in df.columns:
            group_key = "dept_code"
        else:
            raise ValueError("Cannot add lagged columns: no group key available.")

    year_to_prev = {year: years_sorted[idx - 1] for idx, year in enumerate(years_sorted) if idx > 0}
    out = df.copy()
    out["_prev_year"] = out["year"].map(year_to_prev)

    prev_df = out[["year", group_key] + lag_cols].copy()
    rename_map = {"year": "_prev_year"}
    rename_map.update({col: f"{col}_prev" for col in lag_cols})
    prev_df = prev_df.rename(columns=rename_map)

    out = out.merge(prev_df, on=["_prev_year", group_key], how="left", suffixes=("", "_dup"))
    out = out.drop(columns=["_prev_year"], errors="ignore")
    out = out.loc[:, ~out.columns.duplicated()]

    for col in lag_cols:
        prev_col = f"{col}_prev"
        if prev_col in out.columns:
            out[prev_col] = out[prev_col].fillna(fill_value)

    return out


def add_lagged_features(df: pd.DataFrame, family_columns: list[str]) -> pd.DataFrame:
    """Backward-compatible wrapper for political-share lag features."""
    lag_cols = ["share_winner"] + [col for col in family_columns if col in df.columns]
    return add_lagged_columns(df, lag_cols, fill_value=0.0, group_key="geo_code")


def add_commune_transfer_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add engineered commune-level transfer features derived from previous-election family shares.
    These features help capture vote transfers (centre/extreme pressure) in post-2017 dynamics.
    """
    out = df.copy()

    for col in ["extreme_gauche_prev", "gauche_prev", "centre_prev", "droite_prev", "extreme_droite_prev", "droite_nat_prev"]:
        if col not in out.columns:
            out[col] = 0.0

    out["left_bloc_strength"] = out["extreme_gauche_prev"] + out["gauche_prev"]
    out["right_bloc_strength"] = out["droite_prev"] + out["extreme_droite_prev"] + out["droite_nat_prev"]
    out["center_competition"] = out["centre_prev"]
    out["right_pressure"] = out["extreme_droite_prev"] + out["centre_prev"]
    out["left_pressure"] = out["extreme_gauche_prev"] + out["centre_prev"]
    out["droite_gap_vs_extreme"] = out["droite_prev"] - out["extreme_droite_prev"]
    out["gauche_gap_vs_extreme"] = out["gauche_prev"] - out["extreme_gauche_prev"]
    return out


def build_ml_dataset(
    target: str = "share_winner",
    use_db: bool = True,
    include_lags: bool = True,
    scope: str = "departement",
) -> pd.DataFrame:
    """
    Build the ML dataset with one row per (year, geo_code).
    """
    results_df, socio_df = load_raw_data(use_db=use_db, scope=scope)
    if results_df.empty:
        raise RuntimeError("Aucune donnee electorale disponible. Lancez l'ETL : python -m src.etl.run_etl")

    family_shares = build_family_shares(results_df)
    election_context = build_election_context(results_df)
    socio_pivot = build_socio_pivot(socio_df)

    df = family_shares.merge(election_context, on=["year", "geo_code", "dept_code"], how="left")
    df = df.merge(socio_pivot, on=["year", "dept_code"], how="left")
    if scope == "commune":
        commune_geo = build_commune_geo_features(results_df)
        df = df.merge(commune_geo, on=["year", "geo_code", "dept_code"], how="left")
        commune_odd = _extract_commune_odd_feature_pivot()
        if not commune_odd.empty:
            df = df.merge(commune_odd, on=["year", "geo_code"], how="left")

    family_cols = [col for col in FAMILIES if col in df.columns]
    lag_context_cols = [col for col in ELECTION_CONTEXT_FEATURES if col in df.columns]

    if include_lags:
        lag_cols = ["share_winner"] + family_cols + lag_context_cols
        df = add_lagged_columns(df, lag_cols, fill_value=0.0, group_key="geo_code")
        if scope == "commune":
            df = add_commune_transfer_features(df)

    # Election index (1..N) to capture global temporal trend
    years_ordered = sorted(df["year"].unique())
    year_to_idx = {year: idx + 1 for idx, year in enumerate(years_ordered)}
    df["election_number"] = df["year"].map(year_to_idx)

    # Regression target
    if target == "share_winner":
        df["target"] = df["share_winner"]
    elif target in df.columns:
        df["target"] = df[target]
    else:
        df["target"] = df.get("share_winner", 0.0)

    df["scope"] = scope
    return df
