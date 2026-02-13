from __future__ import annotations

import csv
import hashlib
import io
import os
import re
import unicodedata
import urllib.request
import zipfile
from pathlib import Path

import pandas as pd

from .db import get_conn

IDF_DEPARTMENTS = {
    "75": "Paris",
    "77": "Seine-et-Marne",
    "78": "Yvelines",
    "91": "Essonne",
    "92": "Hauts-de-Seine",
    "93": "Seine-Saint-Denis",
    "94": "Val-de-Marne",
    "95": "Val-d'Oise",
}

TARGET_DEPT_CODES = tuple(
    code.strip()
    for code in os.getenv("TARGET_DEPT_CODES", ",".join(IDF_DEPARTMENTS.keys())).split(",")
    if code.strip()
)

ELECTION_DATE_BY_YEAR = {
    1969: "1969-06-01",
    1974: "1974-05-05",
    1981: "1981-04-26",
    1988: "1988-04-24",
    1995: "1995-04-23",
    2002: "2002-04-21",
    2007: "2007-04-22",
    2012: "2012-04-22",
    2017: "2017-04-23",
    2022: "2022-04-10",
}

FIRST_ROUND_XLSX_URL_BY_YEAR = {
    1969: (
        "https://static.data.gouv.fr/resources/election-presidentielle-1969-resultats-par-"
        "departement/20220419-000314/france-politique.fr-presidentielle-1969.xlsx"
    ),
    1974: (
        "https://static.data.gouv.fr/resources/election-presidentielle-1974-resultats-par-"
        "departement/20160821-213008/France-politique.fr_Presidentielle_1974.xlsx"
    ),
    1981: (
        "https://static.data.gouv.fr/resources/election-presidentielle-1981-resultats-par-"
        "departement/20160821-213523/France-politique.fr_Presidentielle_1981.xlsx"
    ),
    1988: (
        "https://static.data.gouv.fr/resources/election-presidentielle-1988-resultats-par-"
        "departement/20160821-213723/France-politique.fr_Presidentielle_1988.xlsx"
    ),
    1995: (
        "https://static.data.gouv.fr/resources/election-presidentielle-1995-resultats-par-"
        "departement/20160821-213837/France-politique.fr_Presidentielle_1995.xlsx"
    ),
    2002: (
        "https://static.data.gouv.fr/resources/election-presidentielle-2002-resultats-par-"
        "departement/20160821-213930/France-politique.fr_Presidentielle_2002.xlsx"
    ),
    2007: (
        "https://static.data.gouv.fr/resources/election-presidentielle-2007-resultats-par-"
        "departement/20160821-214058/France-politique.fr_Presidentielle_2007.xlsx"
    ),
    2012: (
        "https://static.data.gouv.fr/resources/election-presidentielle-2012-resultats-par-"
        "departement/20160821-214241/France-politique.fr_Presidentielle_2012.xlsx"
    ),
    2022: (
        "https://static.data.gouv.fr/resources/election-presidentielle-2012-resultats-par-"
        "departement-1/20220414-215243/france-politique.fr-presidentielle-2022.xlsx"
    ),
}

FIRST_ROUND_2017_BUREAU_TXT_URL = (
    "https://static.data.gouv.fr/resources/election-presidentielle-des-23-avril-et-7-mai-"
    "2017-resultats-definitifs-du-1er-tour-par-bureaux-de-vote/20170427-100955/PR17_BVot_T1_FE.txt"
)

ODD_DEP_ZIP_URL = "https://www.insee.fr/fr/statistiques/fichier/4505239/ODD_CSV.zip"
ODD_DEP_FILENAME = "ODD_DEP.csv"
SOCIO_SOURCE_LABEL = "INSEE - Indicateurs territoriaux de developpement durable (ODD_DEP)"
ALIGN_SOCIO_TO_ELECTION_YEARS = os.getenv("ALIGN_SOCIO_TO_ELECTION_YEARS", "true").lower() in {
    "1",
    "true",
    "yes",
}

SOCIO_ECO_ODD_SPECS = [
    {
        "indicator_code": "unemployment_rate",
        "indicator_name": "Taux de chomage BIT (15-64 ans)",
        "unit": "%",
        "variable": "taux_chom_bit",
        "sous_champ": "total",
    },
    {
        "indicator_code": "poverty_rate",
        "indicator_name": "Taux de pauvrete",
        "unit": "%",
        "variable": "taux_pvt",
        "sous_champ": "total",
    },
    {
        "indicator_code": "median_standard_of_living",
        "indicator_name": "Niveau de vie median",
        "unit": "EUR",
        "variable": "niveau_vie_median",
        "sous_champ": None,
    },
    {
        "indicator_code": "no_diploma_rate_20_24",
        "indicator_name": "Part des 20-24 ans sortis d'etudes sans diplome",
        "unit": "%",
        "variable": "part_20_24_sortis_nondip",
        "sous_champ": None,
    },
    {
        "indicator_code": "social_housing_share",
        "indicator_name": "Part des logements sociaux",
        "unit": "%",
        "variable": "part_pls",
        "sous_champ": None,
    },
]

CACHE_DIR = Path("data/raw/data_gouv_cache")

METADATA_COLUMNS_NORMALIZED = {
    "departement",
    "depnom",
    "depcode",
    "codedudepartement",
    "libelledudepartement",
    "participation",
    "inscrits",
    "ins",
    "abstentions",
    "votants",
    "blancs",
    "nuls",
    "exprimes",
    "exp",
    "etatsaisie",
    "deptcode",
    "deptname",
}


def _normalize_text(value):
    text = "" if value is None else str(value)
    text = text.strip()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    return re.sub(r"[^a-z0-9]+", "", text)


def _cached_download(url):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:12]
    filename = url.rstrip("/").split("/")[-1]
    local_path = CACHE_DIR / f"{digest}_{filename}"
    if local_path.exists():
        return local_path
    urllib.request.urlretrieve(url, local_path)
    return local_path


DEPT_CODE_BY_NORMALIZED_NAME = {_normalize_text(name): code for code, name in IDF_DEPARTMENTS.items()}
DEPT_CODE_BY_NORMALIZED_NAME.update(
    {
        _normalize_text("SEINE ET MARNE"): "77",
        _normalize_text("HAUTS DE SEINE"): "92",
        _normalize_text("SEINE SAINT DENIS"): "93",
        _normalize_text("VAL DE MARNE"): "94",
        _normalize_text("VAL D OISE"): "95",
        _normalize_text("VAL D'OISE"): "95",
    }
)


def _normalize_dept_code(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return str(int(float(text))).zfill(2)
    except ValueError:
        return text.upper().zfill(2)


def _to_int(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip().replace("\u00a0", "").replace(" ", "")
    if not text:
        return None
    text = text.replace(",", ".")
    text = text.replace("%", "")
    try:
        return int(round(float(text)))
    except ValueError:
        return None


def _to_float(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip().replace("\u00a0", "").replace(" ", "")
    if not text:
        return None
    text = text.replace(",", ".").replace("%", "")
    try:
        return float(text)
    except ValueError:
        return None


def _to_ratio(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip().replace("\u00a0", "").replace(" ", "")
    if not text:
        return None
    text = text.replace(",", ".").replace("%", "")
    try:
        number = float(text)
    except ValueError:
        return None
    return round(number / 100.0, 6)


def _canonical_candidate_name(value):
    text = "" if value is None else str(value)
    text = re.sub(r"_(VOIX|EXP)$", "", text, flags=re.IGNORECASE)
    text = text.replace("_", " ")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"\s+", " ", text).strip()
    return text.upper()


def _first_matching_column(columns, accepted_normalized_names):
    for column in columns:
        if _normalize_text(column) in accepted_normalized_names:
            return column
    return None


def _read_first_round_xlsx_by_department(year, url):
    print(f"[extract] year={year} source=xlsx")
    local_path = _cached_download(url)
    df = pd.read_excel(local_path, sheet_name="Premier tour")
    df.columns = [str(c).strip() for c in df.columns]

    dept_code_col = _first_matching_column(df.columns, {"depcode", "codedudepartement"})
    dept_name_col = _first_matching_column(df.columns, {"depnom", "departement", "libelledudepartement"})

    if dept_code_col:
        df["dept_code"] = df[dept_code_col].map(_normalize_dept_code)
    if dept_name_col:
        df["dept_name"] = df[dept_name_col].astype(str).str.strip()

    if "dept_code" not in df.columns:
        if "dept_name" not in df.columns:
            raise RuntimeError(f"Could not find department columns for year {year}.")
        df["dept_code"] = df["dept_name"].map(
            lambda name: DEPT_CODE_BY_NORMALIZED_NAME.get(_normalize_text(name))
        )

    if "dept_name" not in df.columns:
        df["dept_name"] = df["dept_code"].map(IDF_DEPARTMENTS)

    df = df[df["dept_code"].isin(TARGET_DEPT_CODES)].copy()
    if df.empty:
        return pd.DataFrame(columns=_result_columns())

    registered_col = _first_matching_column(df.columns, {"inscrits", "ins"})
    votes_cast_col = _first_matching_column(df.columns, {"votants"})
    votes_valid_col = _first_matching_column(df.columns, {"exprimes", "exp"})
    participation_col = _first_matching_column(df.columns, {"participation"})

    voix_columns = [col for col in df.columns if col.upper().endswith("_VOIX")]

    records = []
    for _, row in df.iterrows():
        dept_code = row["dept_code"]
        dept_name = row.get("dept_name") or IDF_DEPARTMENTS.get(dept_code, dept_code)

        registered = _to_int(row.get(registered_col)) if registered_col else None
        votes_cast = _to_int(row.get(votes_cast_col)) if votes_cast_col else None
        votes_valid = _to_int(row.get(votes_valid_col)) if votes_valid_col else None

        turnout_rate = None
        if participation_col:
            turnout_rate = _to_ratio(row.get(participation_col))
        elif registered and votes_cast is not None and registered != 0:
            turnout_rate = round(votes_cast / registered, 6)

        if voix_columns:
            candidate_columns = voix_columns
            for voix_col in candidate_columns:
                candidate_name = _canonical_candidate_name(voix_col)
                votes = _to_int(row.get(voix_col))
                exp_col = voix_col[:-5] + "_EXP"
                vote_share = _to_ratio(row.get(exp_col))
                if vote_share is None and votes is not None and votes_valid:
                    vote_share = round(votes / votes_valid, 6)
                if votes is None and vote_share is not None and votes_valid:
                    votes = int(round(votes_valid * vote_share))
                if vote_share is None:
                    continue
                records.append(
                    {
                        "year": year,
                        "dept_code": dept_code,
                        "dept_name": dept_name,
                        "candidate_name": candidate_name,
                        "registered": registered,
                        "votes_cast": votes_cast,
                        "votes_valid": votes_valid,
                        "votes": votes,
                        "vote_share": vote_share,
                        "turnout_rate": turnout_rate,
                    }
                )
            continue

        for col in df.columns:
            if col.startswith("Unnamed"):
                continue
            normalized = _normalize_text(col)
            if normalized in METADATA_COLUMNS_NORMALIZED:
                continue
            raw_value = row.get(col)
            vote_share = _to_ratio(raw_value)
            if vote_share is None:
                continue

            candidate_name = _canonical_candidate_name(col)
            votes = None
            if votes_valid is not None:
                votes = int(round(votes_valid * vote_share))

            records.append(
                {
                    "year": year,
                    "dept_code": dept_code,
                    "dept_name": dept_name,
                    "candidate_name": candidate_name,
                    "registered": registered,
                    "votes_cast": votes_cast,
                    "votes_valid": votes_valid,
                    "votes": votes,
                    "vote_share": vote_share,
                    "turnout_rate": turnout_rate,
                }
            )

    result = pd.DataFrame.from_records(records)
    if result.empty:
        return pd.DataFrame(columns=_result_columns())
    return result[_result_columns()]


def _read_2017_first_round_from_bureau_txt(url):
    print("[extract] year=2017 source=txt")
    local_path = _cached_download(url)
    content = local_path.read_text(encoding="latin-1", errors="replace")

    reader = csv.reader(io.StringIO(content), delimiter=";")
    header = next(reader, None)
    if not header:
        return pd.DataFrame(columns=_result_columns())

    normalized_header = [_normalize_text(h) for h in header]
    idx_by_name = {name: i for i, name in enumerate(normalized_header)}

    required = [
        "codedudepartement",
        "libelledudepartement",
        "codedelacommune",
        "codedubvote",
        "inscrits",
        "votants",
        "exprimes",
        "npanneau",
    ]
    missing = [name for name in required if name not in idx_by_name]
    if missing:
        raise RuntimeError(f"Unexpected 2017 TXT format, missing columns: {missing}")

    candidate_start = idx_by_name["npanneau"]
    chunk_size = 7

    seen_bureaus = set()
    totals_by_dept = {}
    candidate_votes = {}

    for row in reader:
        if len(row) <= candidate_start:
            continue

        dept_code = _normalize_dept_code(row[idx_by_name["codedudepartement"]])
        if dept_code not in TARGET_DEPT_CODES:
            continue

        dept_name = row[idx_by_name["libelledudepartement"]].strip() or IDF_DEPARTMENTS.get(
            dept_code, dept_code
        )
        commune_code = row[idx_by_name["codedelacommune"]].strip()
        bureau_code = row[idx_by_name["codedubvote"]].strip()
        bureau_key = (dept_code, commune_code, bureau_code)

        if bureau_key not in seen_bureaus:
            seen_bureaus.add(bureau_key)
            registered = _to_int(row[idx_by_name["inscrits"]]) or 0
            votes_cast = _to_int(row[idx_by_name["votants"]]) or 0
            votes_valid = _to_int(row[idx_by_name["exprimes"]]) or 0

            current = totals_by_dept.setdefault(
                dept_code,
                {"dept_name": dept_name, "registered": 0, "votes_cast": 0, "votes_valid": 0},
            )
            current["registered"] += registered
            current["votes_cast"] += votes_cast
            current["votes_valid"] += votes_valid

        for i in range(candidate_start, len(row), chunk_size):
            if i + 4 >= len(row):
                break
            panel = row[i].strip()
            if not panel:
                continue
            last_name = row[i + 2].strip()
            votes = _to_int(row[i + 4]) or 0
            candidate_name = _canonical_candidate_name(last_name)
            key = (dept_code, candidate_name)
            candidate_votes[key] = candidate_votes.get(key, 0) + votes

    records = []
    for (dept_code, candidate_name), votes in candidate_votes.items():
        totals = totals_by_dept.get(dept_code, {})
        registered = totals.get("registered")
        votes_cast = totals.get("votes_cast")
        votes_valid = totals.get("votes_valid")
        turnout_rate = None
        vote_share = None

        if registered:
            turnout_rate = round(votes_cast / registered, 6) if votes_cast is not None else None
        if votes_valid:
            vote_share = round(votes / votes_valid, 6)

        records.append(
            {
                "year": 2017,
                "dept_code": dept_code,
                "dept_name": totals.get("dept_name", IDF_DEPARTMENTS.get(dept_code, dept_code)),
                "candidate_name": candidate_name,
                "registered": registered,
                "votes_cast": votes_cast,
                "votes_valid": votes_valid,
                "votes": votes,
                "vote_share": vote_share,
                "turnout_rate": turnout_rate,
            }
        )

    result = pd.DataFrame.from_records(records)
    if result.empty:
        return pd.DataFrame(columns=_result_columns())
    return result[_result_columns()]


def _result_columns():
    return [
        "year",
        "dept_code",
        "dept_name",
        "candidate_name",
        "registered",
        "votes_cast",
        "votes_valid",
        "votes",
        "vote_share",
        "turnout_rate",
    ]


def _collect_all_results():
    all_records = []
    for year, url in sorted(FIRST_ROUND_XLSX_URL_BY_YEAR.items()):
        frame = _read_first_round_xlsx_by_department(year, url)
        if not frame.empty:
            all_records.extend(frame.to_dict(orient="records"))

    frame_2017 = _read_2017_first_round_from_bureau_txt(FIRST_ROUND_2017_BUREAU_TXT_URL)
    if not frame_2017.empty:
        all_records.extend(frame_2017.to_dict(orient="records"))

    if not all_records:
        return pd.DataFrame(columns=_result_columns())

    df = pd.DataFrame.from_records(all_records, columns=_result_columns())
    if df.empty:
        return df

    # Keep one row per year, department and candidate.
    df = (
        df.sort_values(["year", "dept_code", "candidate_name"])
        .groupby(["year", "dept_code", "dept_name", "candidate_name"], as_index=False)
        .agg(
            registered=("registered", "max"),
            votes_cast=("votes_cast", "max"),
            votes_valid=("votes_valid", "max"),
            votes=("votes", lambda s: s.sum(min_count=1)),
            vote_share=("vote_share", "max"),
            turnout_rate=("turnout_rate", "max"),
        )
    )

    # If source includes votes+valid, recompute share from counts for consistency.
    df["votes"] = pd.to_numeric(df["votes"], errors="coerce")
    df["votes_valid"] = pd.to_numeric(df["votes_valid"], errors="coerce")
    df["vote_share"] = pd.to_numeric(df["vote_share"], errors="coerce")
    mask = df["votes"].notna() & df["votes_valid"].notna() & (df["votes_valid"] != 0)
    df.loc[mask, "vote_share"] = (df.loc[mask, "votes"] / df.loc[mask, "votes_valid"]).round(6)
    return df


def _read_odd_dep_dataframe():
    print("[extract] source=insee_odd_dep")
    local_zip_path = _cached_download(ODD_DEP_ZIP_URL)
    with zipfile.ZipFile(local_zip_path) as archive:
        with archive.open(ODD_DEP_FILENAME) as csv_file:
            df = pd.read_csv(csv_file, sep=";", encoding="latin-1", low_memory=False)
    df["codgeo"] = df["codgeo"].map(_normalize_dept_code)
    df = df[df["codgeo"].isin(TARGET_DEPT_CODES)].copy()
    return df


def _source_file_for_spec(spec):
    suffix = f"variable={spec['variable']}"
    if spec["sous_champ"] is not None:
        suffix += f",sous_champ={spec['sous_champ']}"
    return f"{SOCIO_SOURCE_LABEL} ({suffix})"


def _extract_socio_values_from_odd():
    odd_dep_df = _read_odd_dep_dataframe()
    if odd_dep_df.empty:
        return pd.DataFrame(columns=["indicator_code", "insee_code", "year", "value", "source_file"])

    year_columns = sorted(
        [col for col in odd_dep_df.columns if re.fullmatch(r"A\d{4}", str(col))],
        key=lambda col: int(col[1:]),
    )

    records = []
    for spec in SOCIO_ECO_ODD_SPECS:
        mask = odd_dep_df["variable"].astype(str) == spec["variable"]
        if spec["sous_champ"] is None:
            mask &= odd_dep_df["sous_champ"].isna()
        else:
            mask &= odd_dep_df["sous_champ"].fillna("").astype(str).str.strip() == spec["sous_champ"]

        subset = odd_dep_df[mask].copy()
        if subset.empty:
            print(
                f"[warn] no socio values found for {spec['indicator_code']} "
                f"(variable={spec['variable']}, sous_champ={spec['sous_champ']})."
            )
            continue

        source_file = _source_file_for_spec(spec)
        for row in subset.itertuples(index=False):
            insee_code = f"{row.codgeo}000"
            for year_col in year_columns:
                raw_value = getattr(row, year_col)
                value = _to_float(raw_value)
                if value is None:
                    continue
                records.append(
                    {
                        "indicator_code": spec["indicator_code"],
                        "insee_code": insee_code,
                        "year": int(year_col[1:]),
                        "value": value,
                        "source_file": source_file,
                    }
                )

    values_df = pd.DataFrame.from_records(records)
    if values_df.empty:
        return pd.DataFrame(columns=["indicator_code", "insee_code", "year", "value", "source_file"])

    values_df = (
        values_df.sort_values(["indicator_code", "insee_code", "year"])
        .drop_duplicates(subset=["indicator_code", "insee_code", "year"], keep="last")
        .reset_index(drop=True)
    )
    return values_df


def _align_socio_values_to_election_years(values_df):
    if values_df.empty:
        return values_df

    target_years = sorted(ELECTION_DATE_BY_YEAR.keys())
    aligned_records = []

    for (indicator_code, insee_code), group in values_df.groupby(
        ["indicator_code", "insee_code"], as_index=False
    ):
        series = group.sort_values("year").reset_index(drop=True)
        known_years = series["year"].tolist()

        for target_year in target_years:
            exact = series[series["year"] == target_year]
            if not exact.empty:
                source = exact.iloc[-1]
                aligned_records.append(
                    {
                        "indicator_code": indicator_code,
                        "insee_code": insee_code,
                        "year": int(target_year),
                        "value": float(source["value"]),
                        "source_file": source["source_file"],
                    }
                )
                continue

            prior = [year for year in known_years if year <= target_year]
            if not prior:
                continue
            source_year = max(prior)

            source = series[series["year"] == source_year].iloc[-1]
            aligned_records.append(
                {
                    "indicator_code": indicator_code,
                    "insee_code": insee_code,
                    "year": int(target_year),
                    "value": float(source["value"]),
                    "source_file": f"{source['source_file']} [aligned_from={int(source_year)}]",
                }
            )

    aligned_df = pd.DataFrame.from_records(aligned_records)
    return (
        aligned_df.sort_values(["indicator_code", "insee_code", "year"])
        .drop_duplicates(subset=["indicator_code", "insee_code", "year"], keep="last")
        .reset_index(drop=True)
    )


def _collect_socio_indicator_values():
    values_df = _extract_socio_values_from_odd()
    if values_df.empty:
        return values_df

    if ALIGN_SOCIO_TO_ELECTION_YEARS:
        values_df = _align_socio_values_to_election_years(values_df)
    return values_df


def _get_or_create_election(cur, year):
    election_type = "presidentielle"
    election_date = ELECTION_DATE_BY_YEAR[year]
    round_no = 1
    scope = "departement"

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


def _get_or_create_candidate(cur, candidate_name):
    cur.execute(
        """
        SELECT candidate_id
        FROM candidate
        WHERE candidate_name = %s
          AND party_code IS NOT DISTINCT FROM %s
        """,
        (candidate_name, None),
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
        (candidate_name, None),
    )
    return cur.fetchone()[0]


def _ensure_votes_nullable(cur):
    cur.execute(
        """
        SELECT is_nullable
        FROM information_schema.columns
        WHERE table_name = 'election_result' AND column_name = 'votes'
        """
    )
    row = cur.fetchone()
    if row and row[0] == "NO":
        cur.execute("ALTER TABLE election_result ALTER COLUMN votes DROP NOT NULL")


def _ensure_idf_geo(cur):
    cur.executemany(
        """
        INSERT INTO geo_department (dept_code, dept_name)
        VALUES (%s, %s)
        ON CONFLICT (dept_code) DO NOTHING
        """,
        [(code, name) for code, name in IDF_DEPARTMENTS.items() if code in TARGET_DEPT_CODES],
    )

    cur.executemany(
        """
        INSERT INTO geo_commune (insee_code, commune_name, dept_code)
        VALUES (%s, %s, %s)
        ON CONFLICT (insee_code) DO UPDATE
        SET commune_name = EXCLUDED.commune_name,
            dept_code = EXCLUDED.dept_code
        """,
        [
            (f"{code}000", f"{IDF_DEPARTMENTS[code]} (departement)", code)
            for code in TARGET_DEPT_CODES
            if code in IDF_DEPARTMENTS
        ],
    )


def _ensure_indicator_catalog(cur):
    cur.executemany(
        """
        INSERT INTO indicator (indicator_code, indicator_name, unit, source)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (indicator_code) DO NOTHING
        """,
        [
            (
                spec["indicator_code"],
                spec["indicator_name"],
                spec["unit"],
                SOCIO_SOURCE_LABEL,
            )
            for spec in SOCIO_ECO_ODD_SPECS
        ],
    )

    cur.execute(
        """
        INSERT INTO indicator (indicator_code, indicator_name, unit, source)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (indicator_code) DO NOTHING
        """,
        ("turnout_rate", "Taux de participation", "%", "Resultats election data.gouv"),
    )


def _load_turnout_indicator_values(cur, results_df):
    cur.execute("SELECT indicator_id FROM indicator WHERE indicator_code = %s", ("turnout_rate",))
    row = cur.fetchone()
    if not row:
        return
    indicator_id = row[0]

    turnout_rows = (
        results_df[["year", "dept_code", "turnout_rate"]]
        .dropna(subset=["turnout_rate"])
        .drop_duplicates(subset=["year", "dept_code"])
    )
    if turnout_rows.empty:
        return

    payload = [
        (
            indicator_id,
            f"{r.dept_code}000",
            int(r.year),
            float(r.turnout_rate),
            "data.gouv - presidentielle premier tour",
        )
        for r in turnout_rows.itertuples(index=False)
    ]

    cur.executemany(
        """
        INSERT INTO indicator_value (indicator_id, insee_code, year, value, source_file)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (indicator_id, insee_code, year) DO UPDATE
        SET value = EXCLUDED.value,
            source_file = EXCLUDED.source_file
        """,
        payload,
    )


def _load_socio_indicator_values(cur, values_df):
    if values_df.empty:
        print("[warn] no socio-economic values to load.")
        return

    indicator_codes = sorted(values_df["indicator_code"].dropna().unique().tolist())
    cur.execute(
        """
        SELECT indicator_id, indicator_code
        FROM indicator
        WHERE indicator_code = ANY(%s)
        """,
        (indicator_codes,),
    )
    indicator_id_by_code = {code: indicator_id for indicator_id, code in cur.fetchall()}

    payload = []
    for row in values_df.itertuples(index=False):
        indicator_id = indicator_id_by_code.get(row.indicator_code)
        if indicator_id is None:
            continue
        payload.append(
            (
                indicator_id,
                row.insee_code,
                int(row.year),
                float(row.value),
                row.source_file,
            )
        )

    if not payload:
        print("[warn] socio-economic payload is empty after indicator lookup.")
        return

    cur.executemany(
        """
        INSERT INTO indicator_value (indicator_id, insee_code, year, value, source_file)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (indicator_id, insee_code, year) DO UPDATE
        SET value = EXCLUDED.value,
            source_file = EXCLUDED.source_file
        """,
        payload,
    )
    print(
        f"[load] socio indicators rows={len(payload)} "
        f"indicators={values_df['indicator_code'].nunique()} "
        f"departments={values_df['insee_code'].nunique()}"
    )


def _to_db_int(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    return int(value)


def _load_election_results(results_df):
    if results_df.empty:
        print("No election rows extracted from data.gouv.")
        return

    conn = get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                _ensure_votes_nullable(cur)
                _ensure_idf_geo(cur)
                _ensure_indicator_catalog(cur)

                candidate_cache = {}
                target_insee = [f"{code}000" for code in TARGET_DEPT_CODES]

                for year in sorted(results_df["year"].unique()):
                    election_id = _get_or_create_election(cur, int(year))

                    cur.execute(
                        """
                        DELETE FROM election_result
                        WHERE election_id = %s AND insee_code = ANY(%s)
                        """,
                        (election_id, target_insee),
                    )

                    year_df = results_df[results_df["year"] == year]
                    rows = []
                    for record in year_df.itertuples(index=False):
                        candidate_name = record.candidate_name
                        if candidate_name not in candidate_cache:
                            candidate_cache[candidate_name] = _get_or_create_candidate(
                                cur, candidate_name
                            )

                        rows.append(
                            (
                                election_id,
                                f"{record.dept_code}000",
                                candidate_cache[candidate_name],
                                _to_db_int(record.registered),
                                _to_db_int(record.votes_cast),
                                _to_db_int(record.votes_valid),
                                _to_db_int(record.votes),
                                None if pd.isna(record.vote_share) else float(record.vote_share),
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

                    print(
                        f"[load] year={int(year)} rows={len(rows)} departments="
                        f"{year_df['dept_code'].nunique()}"
                    )

                _load_turnout_indicator_values(cur, results_df)
    finally:
        conn.close()


def run_election_pipeline():
    results_df = _collect_all_results()
    if results_df.empty:
        raise RuntimeError("No election data extracted. Check source URLs in run_etl.py.")

    _load_election_results(results_df)
    print(
        "[done] loaded election results for years "
        f"{', '.join(str(y) for y in sorted(results_df['year'].unique()))} "
        f"on target departments {', '.join(sorted(TARGET_DEPT_CODES))}."
    )


def collect_election_results_dataframe():
    return _collect_all_results()


def collect_socio_indicator_values_dataframe():
    return _collect_socio_indicator_values()


def run_socio_economic_pipeline():
    values_df = _collect_socio_indicator_values()
    if values_df.empty:
        raise RuntimeError("No socio-economic values extracted from INSEE ODD dataset.")

    conn = get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                _ensure_idf_geo(cur)
                _ensure_indicator_catalog(cur)
                _load_socio_indicator_values(cur, values_df)
    finally:
        conn.close()

    print(
        "[done] loaded socio-economic indicator values for years "
        f"{values_df['year'].min()}-{values_df['year'].max()} "
        f"(rows={len(values_df)})."
    )


def main():
    run_election_pipeline()
    run_socio_economic_pipeline()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
