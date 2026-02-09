from pathlib import Path
import os

import pandas as pd

from .db import get_conn

RAW_DIR = Path("data/raw/presidentielle_2002/Resultats_elections_presidentielles_2002")
FILE_BY_ROUND = {
    1: "PR02_T1_BVot.csv",
    2: "PR02_T2_BVot.csv",
}
ELECTION_DATE_BY_ROUND = {
    1: "2002-04-21",
    2: "2002-05-05",
}

DEPT_CODE = os.getenv("DEPT_CODE", "34")

COLUMNS = [
    "round",
    "dept_code",
    "commune_code",
    "commune_name",
    "bureau",
    "registered",
    "voters",
    "valid",
    "candidate_deposit_no",
    "last_name",
    "first_name",
    "candidate_sigle",
    "votes",
]


def _read_round(round_no):
    path = RAW_DIR / FILE_BY_ROUND[round_no]
    if not path.exists():
        raise FileNotFoundError(path)

    df = pd.read_csv(
        path,
        sep=";",
        comment="-",
        header=None,
        names=COLUMNS,
        encoding="latin-1",
        dtype=str,
    )
    df = df[df["dept_code"] == DEPT_CODE].copy()
    if df.empty:
        return df

    for col in ["registered", "voters", "valid", "votes"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

    df["commune_code"] = df["commune_code"].str.zfill(3)
    df["insee_code"] = df["dept_code"] + df["commune_code"]

    df["candidate_sigle"] = df["candidate_sigle"].fillna("").str.strip()
    df["candidate_name"] = (
        df["last_name"].fillna("").str.strip()
        + " "
        + df["first_name"].fillna("").str.strip()
    ).str.strip()

    return df


def _get_or_create_election(cur, round_no):
    election_type = "presidentielle"
    election_date = ELECTION_DATE_BY_ROUND[round_no]
    scope = "commune"

    cur.execute(
        """
        SELECT election_id
        FROM election
        WHERE election_type = %s AND election_date = %s AND round = %s AND scope = %s
        """,
        (election_type, election_date, round_no, scope),
    )
    row = cur.fetchone()
    if row:
        return row[0]

    cur.execute(
        """
        INSERT INTO election (election_type, election_date, round, scope)
        VALUES (%s, %s, %s, %s)
        RETURNING election_id
        """,
        (election_type, election_date, round_no, scope),
    )
    return cur.fetchone()[0]


def _get_or_create_candidate(cur, candidate_name, candidate_sigle):
    cur.execute(
        """
        SELECT candidate_id
        FROM candidate
        WHERE candidate_name = %s AND party_code = %s
        """,
        (candidate_name, candidate_sigle),
    )
    row = cur.fetchone()
    if row:
        return row[0]

    cur.execute(
        """
        INSERT INTO candidate (candidate_name, party_code)
        VALUES (%s, %s)
        RETURNING candidate_id
        """,
        (candidate_name, candidate_sigle),
    )
    return cur.fetchone()[0]


def _load_round(round_no):
    df = _read_round(round_no)
    if df.empty:
        print(f"No rows for dept {DEPT_CODE} in round {round_no}.")
        return

    bureau_totals = df[["insee_code", "bureau", "registered", "voters", "valid"]].drop_duplicates()
    commune_totals = (
        bureau_totals.groupby("insee_code", as_index=False)[["registered", "voters", "valid"]].sum()
    )

    vote_totals = (
        df.groupby(["insee_code", "candidate_name", "candidate_sigle"], as_index=False)["votes"].sum()
    )

    vote_totals = vote_totals.merge(commune_totals, on="insee_code", how="left")
    valid_nonzero = vote_totals["valid"].where(vote_totals["valid"] != 0)
    vote_totals["vote_share"] = (vote_totals["votes"] / valid_nonzero).round(6)

    communes = df[["insee_code", "commune_name", "dept_code"]].drop_duplicates()

    conn = get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                election_id = _get_or_create_election(cur, round_no)

                cur.executemany(
                    """
                    INSERT INTO geo_commune (insee_code, commune_name, dept_code)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (insee_code) DO NOTHING
                    """,
                    communes.itertuples(index=False, name=None),
                )

                candidate_cache = {}
                for candidate_name, candidate_sigle in (
                    df[["candidate_name", "candidate_sigle"]].drop_duplicates().itertuples(index=False, name=None)
                ):
                    candidate_id = _get_or_create_candidate(cur, candidate_name, candidate_sigle)
                    candidate_cache[(candidate_name, candidate_sigle)] = candidate_id

                cur.execute(
                    """
                    DELETE FROM election_result
                    WHERE election_id = %s AND insee_code LIKE %s
                    """,
                    (election_id, f"{DEPT_CODE}%"),
                )

                rows = []
                for row in vote_totals.itertuples(index=False):
                    candidate_id = candidate_cache[(row.candidate_name, row.candidate_sigle)]
                    rows.append(
                        (
                            election_id,
                            row.insee_code,
                            candidate_id,
                            int(row.registered),
                            int(row.voters),
                            int(row.valid),
                            int(row.votes),
                            None if pd.isna(row.vote_share) else float(row.vote_share),
                        )
                    )

                cur.executemany(
                    """
                    INSERT INTO election_result (
                        election_id,
                        insee_code,
                        candidate_id,
                        registered,
                        votes_cast,
                        votes_valid,
                        votes,
                        vote_share
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    rows,
                )
    finally:
        conn.close()

    print(
        f"Loaded round {round_no}: {len(vote_totals)} candidate rows across {len(commune_totals)} communes."
    )


def main():
    available_rounds = [
        round_no for round_no, fname in FILE_BY_ROUND.items() if (RAW_DIR / fname).exists()
    ]
    if not available_rounds:
        print("No raw election files found. See docs/sources.md.")
        return 1

    for round_no in sorted(available_rounds):
        _load_round(round_no)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
