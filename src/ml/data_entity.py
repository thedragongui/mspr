"""
ML dataset builder for candidate-level and party-lineage-level predictions.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .data import (
    COMMUNE_THEMATIC_DB_FEATURES,
    ELECTION_CONTEXT_FEATURES,
    FAMILIES,
    _extract_commune_odd_feature_pivot,
    _merge_commune_thematic_features,
    _merge_latest_municipal_context,
    add_commune_transfer_features,
    add_lagged_columns,
    add_presidential_temporal_features,
    build_commune_geo_features,
    build_election_context,
    build_family_shares,
    build_socio_pivot,
    load_raw_data,
)
from .entity_mapping import (
    candidate_display_name,
    canonical_candidate_from_input,
    canonical_candidate_id,
    canonical_party_lineage,
    canonical_party_lineage_from_input,
)
from .features import get_family, get_family_from_party_code

ENTITY_MODES = {"candidate", "party"}


def _ensure_geo_columns(results_df: pd.DataFrame, scope: str) -> pd.DataFrame:
    out = results_df.copy()
    if "geo_code" not in out.columns:
        if scope == "commune" and "insee_code" in out.columns:
            out["geo_code"] = out["insee_code"].astype(str).str.strip().str.zfill(5)
        else:
            out["geo_code"] = out["dept_code"].astype(str).str.zfill(2) + "000"
    out["dept_code"] = out["dept_code"].astype(str).str.strip().str.zfill(2)
    out["geo_code"] = out["geo_code"].astype(str).str.strip()
    out["year"] = pd.to_numeric(out["year"], errors="coerce").astype("Int64")
    out = out.dropna(subset=["year"]).copy()
    out["year"] = out["year"].astype(int)
    return out


def enrich_results_with_entities(results_df: pd.DataFrame, scope: str) -> pd.DataFrame:
    if results_df.empty:
        return pd.DataFrame()
    out = _ensure_geo_columns(results_df, scope=scope)
    out["candidate_name"] = out["candidate_name"].astype(str).str.strip().str.upper()
    out["vote_share"] = pd.to_numeric(out["vote_share"], errors="coerce")
    out = out.dropna(subset=["vote_share"]).copy()

    out["candidate_id"] = out.apply(
        lambda row: canonical_candidate_id(
            candidate_name=row.get("candidate_name"),
            year=int(row.get("year")) if pd.notna(row.get("year")) else None,
            party_code=row.get("party_code"),
        ),
        axis=1,
    )
    out["candidate_label"] = out["candidate_id"].map(candidate_display_name)
    out["party_lineage"] = out.apply(
        lambda row: canonical_party_lineage(
            party_code=row.get("party_code"),
            party_name=row.get("party_name"),
            candidate_id=row.get("candidate_id"),
        ),
        axis=1,
    )

    out["family"] = out["candidate_name"].map(get_family)
    if "party_code" in out.columns:
        missing_mask = out["family"].isna() | (out["family"] == "autre")
        if missing_mask.any():
            out.loc[missing_mask, "family"] = (
                out.loc[missing_mask, "party_code"]
                .map(get_family_from_party_code)
                .fillna(out.loc[missing_mask, "family"])
            )
    return out


def list_available_entities(
    entity_mode: str = "candidate",
    use_db: bool = True,
    scope: str = "commune",
) -> pd.DataFrame:
    if entity_mode not in ENTITY_MODES:
        raise RuntimeError(f"Unsupported entity_mode: {entity_mode}")

    results_df, _ = load_raw_data(use_db=use_db, scope=scope)
    if results_df.empty:
        return pd.DataFrame()
    enriched = enrich_results_with_entities(results_df, scope=scope)
    if enriched.empty:
        return pd.DataFrame()

    if entity_mode == "candidate":
        summary = (
            enriched.groupby(["candidate_id", "candidate_label"], as_index=False)
            .agg(
                rows=("vote_share", "size"),
                years_min=("year", "min"),
                years_max=("year", "max"),
                years_n=("year", "nunique"),
                party_lineage_count=("party_lineage", "nunique"),
            )
            .sort_values(["years_n", "rows"], ascending=[False, False])
            .reset_index(drop=True)
        )
        return summary

    top_candidate_by_lineage = (
        enriched.groupby(["party_lineage", "candidate_label"], as_index=False)["vote_share"]
        .sum()
        .sort_values(["party_lineage", "vote_share"], ascending=[True, False])
        .groupby("party_lineage", as_index=False)
        .first()
        .rename(columns={"candidate_label": "top_candidate_label"})
    )
    summary = (
        enriched.groupby("party_lineage", as_index=False)
        .agg(
            rows=("vote_share", "size"),
            years_min=("year", "min"),
            years_max=("year", "max"),
            years_n=("year", "nunique"),
            candidate_count=("candidate_id", "nunique"),
        )
        .merge(top_candidate_by_lineage[["party_lineage", "top_candidate_label"]], on="party_lineage", how="left")
        .sort_values(["years_n", "rows"], ascending=[False, False])
        .reset_index(drop=True)
    )
    return summary


def _target_from_enriched(
    enriched: pd.DataFrame,
    entity_mode: str,
    entity_id: str,
) -> tuple[pd.DataFrame, list[int], str]:
    key_cols = ["year", "geo_code", "dept_code"]

    if entity_mode == "candidate":
        target_raw = enriched[enriched["candidate_id"] == entity_id].copy()
        if target_raw.empty:
            raise RuntimeError(f"Aucune ligne pour le candidat '{entity_id}'.")
        target_df = (
            target_raw.groupby(key_cols, as_index=False)["vote_share"]
            .sum()
            .rename(columns={"vote_share": "target_share"})
        )
        years_present = sorted(target_raw["year"].dropna().astype(int).unique().tolist())
        entity_label = candidate_display_name(entity_id)
        return target_df, years_present, entity_label

    target_raw = enriched[enriched["party_lineage"] == entity_id].copy()
    if target_raw.empty:
        raise RuntimeError(f"Aucune ligne pour le parti/lineage '{entity_id}'.")
    target_df = (
        target_raw.groupby(key_cols, as_index=False)["vote_share"]
        .sum()
        .rename(columns={"vote_share": "target_share"})
    )
    years_present = sorted(target_raw["year"].dropna().astype(int).unique().tolist())
    entity_label = entity_id
    return target_df, years_present, entity_label


def _resolve_candidate_entity_id(enriched: pd.DataFrame, requested_entity: str) -> str:
    candidate_ids = sorted(set(enriched["candidate_id"].dropna().astype(str).tolist()))
    if not candidate_ids:
        raise RuntimeError("Aucun candidat disponible dans les donnees.")

    requested_id = canonical_candidate_from_input(requested_entity)
    if requested_id in candidate_ids:
        return requested_id

    # Ambiguous shorthand "LE PEN" -> select the most recent available lineage member.
    if requested_id == "LE_PEN":
        candidate_last_year = (
            enriched.groupby("candidate_id", as_index=False)["year"].max().set_index("candidate_id")["year"].to_dict()
        )
        options = [cid for cid in ["MARINE_LE_PEN", "JEAN_MARIE_LE_PEN"] if cid in candidate_last_year]
        if options:
            options = sorted(options, key=lambda cid: int(candidate_last_year[cid]), reverse=True)
            return options[0]

    # Soft fallback by token overlap.
    token = str(requested_id).strip().upper()
    overlaps = [cid for cid in candidate_ids if token in cid or cid in token]
    if overlaps:
        candidate_last_year = (
            enriched.groupby("candidate_id", as_index=False)["year"].max().set_index("candidate_id")["year"].to_dict()
        )
        overlaps = sorted(overlaps, key=lambda cid: int(candidate_last_year.get(cid, 0)), reverse=True)
        return overlaps[0]

    raise RuntimeError(
        f"Candidat '{requested_entity}' introuvable. "
        f"Essayez --list-entities pour obtenir les identifiants disponibles."
    )


def build_entity_ml_dataset(
    entity: str,
    entity_mode: str = "candidate",
    use_db: bool = True,
    include_lags: bool = True,
    scope: str = "commune",
    include_absent_years: bool = False,
) -> tuple[pd.DataFrame, dict]:
    """
    Build one-row-per-(year,geo_code) dataset for a target candidate or party lineage.
    """
    if entity_mode not in ENTITY_MODES:
        raise RuntimeError(f"Unsupported entity_mode: {entity_mode}")
    if scope not in {"departement", "commune"}:
        raise RuntimeError(f"Unsupported scope: {scope}")

    results_df, socio_df = load_raw_data(use_db=use_db, scope=scope)
    if results_df.empty:
        raise RuntimeError("Aucune donnee electorale disponible.")

    enriched = enrich_results_with_entities(results_df, scope=scope)
    if enriched.empty:
        raise RuntimeError("Aucune donnee electorale exploitable apres normalisation entites.")

    if entity_mode == "candidate":
        entity_id = _resolve_candidate_entity_id(enriched=enriched, requested_entity=entity)
    else:
        entity_id = canonical_party_lineage_from_input(entity)

    target_df, years_present, entity_label = _target_from_enriched(
        enriched=enriched,
        entity_mode=entity_mode,
        entity_id=entity_id,
    )

    key_cols = ["year", "geo_code", "dept_code"]
    panel_keys = enriched[key_cols].drop_duplicates().copy()
    if not include_absent_years:
        panel_keys = panel_keys[panel_keys["year"].isin(years_present)].copy()

    panel = panel_keys.merge(target_df, on=key_cols, how="left")
    panel["target_share"] = pd.to_numeric(panel["target_share"], errors="coerce").fillna(0.0).clip(0.0, 1.0)

    # Build party-lineage context for the selected entity.
    if entity_mode == "candidate":
        dominant_lineage = (
            enriched[enriched["candidate_id"] == entity_id]["party_lineage"]
            .dropna()
            .astype(str)
            .value_counts()
            .index.tolist()
        )
        lineage_id = dominant_lineage[0] if dominant_lineage else canonical_party_lineage(None, None, entity_id)
    else:
        lineage_id = entity_id

    lineage_df = (
        enriched[enriched["party_lineage"] == lineage_id]
        .groupby(key_cols, as_index=False)["vote_share"]
        .sum()
        .rename(columns={"vote_share": "lineage_share"})
    )
    panel = panel.merge(lineage_df, on=key_cols, how="left")
    panel["lineage_share"] = pd.to_numeric(panel["lineage_share"], errors="coerce").fillna(0.0).clip(0.0, 1.0)

    # Political-family context
    family_shares = build_family_shares(enriched)
    if not family_shares.empty:
        panel = panel.merge(family_shares, on=key_cols, how="left")

    # Election context + socio
    election_context = build_election_context(_ensure_geo_columns(results_df, scope=scope))
    panel = panel.merge(election_context, on=key_cols, how="left")

    socio_pivot = build_socio_pivot(socio_df)
    panel = panel.merge(socio_pivot, on=["year", "dept_code"], how="left")

    if scope == "commune":
        commune_geo = build_commune_geo_features(_ensure_geo_columns(results_df, scope=scope))
        panel = panel.merge(commune_geo, on=key_cols, how="left")

        commune_odd = _extract_commune_odd_feature_pivot()
        if not commune_odd.empty:
            panel = panel.merge(commune_odd, on=["year", "geo_code"], how="left")

        panel = _merge_commune_thematic_features(panel, use_db=use_db)
        panel = _merge_latest_municipal_context(panel, use_db=use_db)

    family_cols = [col for col in FAMILIES if col in panel.columns]
    lag_context_cols = [col for col in ELECTION_CONTEXT_FEATURES if col in panel.columns]

    if include_lags:
        lag_cols = ["target_share", "lineage_share", "share_winner"] + family_cols + lag_context_cols
        lag_cols = [col for col in lag_cols if col in panel.columns]
        panel = add_lagged_columns(panel, lag_cols, fill_value=0.0, group_key="geo_code")
        panel = add_lagged_columns(panel, lag_cols, fill_value=0.0, group_key="geo_code", lag_steps=2)
        panel = add_commune_transfer_features(panel)
        panel = add_presidential_temporal_features(panel)

        if {"target_share_prev", "target_share_prev2"}.issubset(panel.columns):
            panel["target_share_momentum"] = (
                pd.to_numeric(panel["target_share_prev"], errors="coerce").fillna(0.0)
                - pd.to_numeric(panel["target_share_prev2"], errors="coerce").fillna(0.0)
            )
        if {"lineage_share_prev", "lineage_share_prev2"}.issubset(panel.columns):
            panel["lineage_share_momentum"] = (
                pd.to_numeric(panel["lineage_share_prev"], errors="coerce").fillna(0.0)
                - pd.to_numeric(panel["lineage_share_prev2"], errors="coerce").fillna(0.0)
            )

    years_ordered = sorted(panel["year"].dropna().astype(int).unique().tolist())
    year_to_idx = {year: idx + 1 for idx, year in enumerate(years_ordered)}
    panel["election_number"] = panel["year"].map(year_to_idx)

    panel["target"] = pd.to_numeric(panel["target_share"], errors="coerce").fillna(0.0).clip(0.0, 1.0)
    panel["entity_mode"] = entity_mode
    panel["entity_id"] = entity_id
    panel["entity_label"] = entity_label
    panel["lineage_id"] = lineage_id
    panel["scope"] = scope

    metadata = {
        "entity_mode": entity_mode,
        "entity_id": entity_id,
        "entity_label": entity_label,
        "lineage_id": lineage_id,
        "years_present": years_present,
        "scope": scope,
        "include_absent_years": bool(include_absent_years),
    }
    return panel, metadata
