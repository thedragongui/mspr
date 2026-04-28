from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from . import run_etl


OUTPUT_DIR = Path("data/clean")
ELECTION_OUTPUT = OUTPUT_DIR / "election_results_commune_t1_idf_clean.csv"
SOCIO_OUTPUT = OUTPUT_DIR / "socio_indicators_idf_clean.csv"
MANIFEST_OUTPUT = OUTPUT_DIR / "manifest.json"

IDF_DEPT_CODES = {"75", "77", "78", "91", "92", "93", "94", "95"}


def _normalize_election_results(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    out = df.copy()

    out["year"] = pd.to_numeric(out["year"], errors="coerce")
    out["insee_code"] = out["insee_code"].astype(str).str.strip().str.zfill(5)
    out["dept_code"] = out["dept_code"].astype(str).str.strip().str.zfill(2)
    out["commune_name"] = out["commune_name"].fillna("").astype(str).str.strip()
    out["candidate_name"] = out["candidate_name"].fillna("").astype(str).str.strip().str.upper()

    for column in ["registered", "votes_cast", "votes_valid", "votes"]:
        out[column] = pd.to_numeric(out[column], errors="coerce")

    out["vote_share"] = pd.to_numeric(out["vote_share"], errors="coerce")
    out["turnout_rate"] = pd.to_numeric(out["turnout_rate"], errors="coerce")

    # Drop rows with incomplete business keys or missing target value.
    out = out.dropna(subset=["year", "vote_share"])
    out = out[out["candidate_name"] != ""]
    out = out[out["insee_code"].str.len() == 5]
    out = out[out["dept_code"].isin(IDF_DEPT_CODES)]

    # Keep only coherent ratios and non-negative counters.
    out = out[(out["vote_share"] >= 0.0) & (out["vote_share"] <= 1.0)]
    out = out[(out["turnout_rate"].isna()) | ((out["turnout_rate"] >= 0.0) & (out["turnout_rate"] <= 1.0))]
    for column in ["registered", "votes_cast", "votes_valid", "votes"]:
        out = out[(out[column].isna()) | (out[column] >= 0)]

    # Recompute vote_share when votes and votes_valid are both available.
    mask = out["votes"].notna() & out["votes_valid"].notna() & (out["votes_valid"] > 0)
    out.loc[mask, "vote_share"] = (out.loc[mask, "votes"] / out.loc[mask, "votes_valid"]).round(6)

    # Keep one unique row per election/candidate/commune.
    out = (
        out.sort_values(["year", "insee_code", "candidate_name"])
        .groupby(["year", "insee_code", "commune_name", "dept_code", "candidate_name"], as_index=False)
        .agg(
            registered=("registered", "max"),
            votes_cast=("votes_cast", "max"),
            votes_valid=("votes_valid", "max"),
            votes=("votes", "max"),
            vote_share=("vote_share", "max"),
            turnout_rate=("turnout_rate", "max"),
        )
    )

    out["year"] = out["year"].astype(int)
    out = out.sort_values(["year", "dept_code", "insee_code", "candidate_name"]).reset_index(drop=True)
    return out[
        [
            "year",
            "insee_code",
            "commune_name",
            "dept_code",
            "candidate_name",
            "registered",
            "votes_cast",
            "votes_valid",
            "votes",
            "vote_share",
            "turnout_rate",
        ]
    ]


def _normalize_socio_indicators(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    out = df.copy()
    out["indicator_code"] = out["indicator_code"].fillna("").astype(str).str.strip()
    out["insee_code"] = out["insee_code"].astype(str).str.strip().str.zfill(5)
    out["year"] = pd.to_numeric(out["year"], errors="coerce")
    out["value"] = pd.to_numeric(out["value"], errors="coerce")
    out["source_file"] = out["source_file"].fillna("").astype(str).str.strip()

    out = out.dropna(subset=["year", "value"])
    out = out[out["indicator_code"] != ""]
    out = out[out["insee_code"].str.len() == 5]
    out = out[out["insee_code"].str[:2].isin(IDF_DEPT_CODES)]

    out["year"] = out["year"].astype(int)
    out = (
        out.sort_values(["indicator_code", "insee_code", "year"])
        .drop_duplicates(subset=["indicator_code", "insee_code", "year"], keep="last")
        .reset_index(drop=True)
    )
    return out[["indicator_code", "insee_code", "year", "value", "source_file"]]


def export_clean_datasets() -> dict[str, int]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    election_df = run_etl.collect_election_results_commune_dataframe()
    socio_df = run_etl.collect_socio_indicator_values_dataframe()

    clean_election = _normalize_election_results(election_df)
    clean_socio = _normalize_socio_indicators(socio_df)

    if clean_election.empty:
        raise RuntimeError("No cleaned election data produced.")
    if clean_socio.empty:
        raise RuntimeError("No cleaned socio indicators produced.")

    clean_election.to_csv(ELECTION_OUTPUT, index=False)
    clean_socio.to_csv(SOCIO_OUTPUT, index=False)

    manifest = {
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "files": {
            str(ELECTION_OUTPUT).replace("\\", "/"): int(len(clean_election)),
            str(SOCIO_OUTPUT).replace("\\", "/"): int(len(clean_socio)),
        },
        "geo_scope": "ile-de-france",
        "analysis_granularity": "commune",
    }
    MANIFEST_OUTPUT.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return {
        "election_rows": int(len(clean_election)),
        "socio_rows": int(len(clean_socio)),
    }


def main() -> int:
    stats = export_clean_datasets()
    print(
        "[done] exported cleaned datasets: "
        f"election_rows={stats['election_rows']}, socio_rows={stats['socio_rows']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
