from __future__ import annotations

import csv
import hashlib
import io
import json
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

MUNICIPAL_ELECTION_DATE_BY_YEAR = {
    2001: "2001-03-11",
    2008: "2008-03-09",
    2014: "2014-03-23",
    2020: "2020-03-15",
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

FIRST_ROUND_CIRC_CSV_URL_BY_YEAR = {
    1969: (
        "https://static.data.gouv.fr/resources/elections-presidentielles-1965-2012-1/"
        "20150204-183627/cdsp_presi1969t1_circ.csv"
    ),
    1974: (
        "https://static.data.gouv.fr/resources/elections-presidentielles-1965-2012-1/"
        "20150204-183637/cdsp_presi1974t1_circ.csv"
    ),
    1981: (
        "https://static.data.gouv.fr/resources/elections-presidentielles-1965-2012-1/"
        "20150204-183645/cdsp_presi1981t1_circ.csv"
    ),
    1988: (
        "https://static.data.gouv.fr/resources/elections-presidentielles-1965-2012-1/"
        "20150204-183654/cdsp_presi1988t1_circ.csv"
    ),
    1995: (
        "https://static.data.gouv.fr/resources/elections-presidentielles-1965-2012-1/"
        "20150204-183707/cdsp_presi1995t1_circ.csv"
    ),
    2002: (
        "https://static.data.gouv.fr/resources/elections-presidentielles-1965-2012-1/"
        "20150204-183716/cdsp_presi2002t1_circ.csv"
    ),
    2007: (
        "https://static.data.gouv.fr/resources/elections-presidentielles-1965-2012-1/"
        "20150204-183726/cdsp_presi2007t1_circ.csv"
    ),
    2012: (
        "https://static.data.gouv.fr/resources/elections-presidentielles-1965-2012-1/"
        "20150204-183733/cdsp_presi2012t1_circ.csv"
    ),
}

FIRST_ROUND_2017_BUREAU_TXT_URL = (
    "https://static.data.gouv.fr/resources/election-presidentielle-des-23-avril-et-7-mai-"
    "2017-resultats-definitifs-du-1er-tour-par-bureaux-de-vote/20170427-100955/PR17_BVot_T1_FE.txt"
)

FIRST_ROUND_2007_BUREAU_T1T2_TXT_URL = (
    "https://static.data.gouv.fr/resources/election-presidentielle-2007-resultats-par-bureaux-de-vote/"
    "20151001-154056/PR07_Bvot_T1T2.txt"
)

FIRST_ROUND_2012_BUREAU_T1T2_TXT_URL = (
    "https://static.data.gouv.fr/resources/election-presidentielle-2012-resultats-par-bureaux-de-vote-1/"
    "20150925-102751/PR12_Bvot_T1T2.txt"
)

FIRST_ROUND_2022_BUREAU_TXT_URL = (
    "https://static.data.gouv.fr/resources/election-presidentielle-des-10-et-24-avril-2022-"
    "resultats-definitifs-du-1er-tour/20220414-152542/resultats-par-niveau-burvot-t1-france-entiere.txt"
)

COMMUNE_BUREAU_SOURCE_URL_BY_YEAR = {
    2007: FIRST_ROUND_2007_BUREAU_T1T2_TXT_URL,
    2012: FIRST_ROUND_2012_BUREAU_T1T2_TXT_URL,
    2017: FIRST_ROUND_2017_BUREAU_TXT_URL,
    2022: FIRST_ROUND_2022_BUREAU_TXT_URL,
}

FIRST_ROUND_COMMP9000_CSV_URL_BY_YEAR = {
    1981: (
        "https://static.data.gouv.fr/resources/elections-presidentielles-1965-2012-1/"
        "20150204-183649/cdsp_presi1981t1_commp9000.csv"
    ),
    1988: (
        "https://static.data.gouv.fr/resources/elections-presidentielles-1965-2012-1/"
        "20150204-183657/cdsp_presi1988t1_commp9000.csv"
    ),
    1995: (
        "https://static.data.gouv.fr/resources/elections-presidentielles-1965-2012-1/"
        "20150204-183710/cdsp_presi1995t1_commp9000.csv"
    ),
    2002: (
        "https://static.data.gouv.fr/resources/elections-presidentielles-1965-2012-1/"
        "20150204-183718/cdsp_presi2002t1_commp9000.csv"
    ),
}

ODD_DEP_ZIP_URL = "https://www.insee.fr/fr/statistiques/fichier/4505239/ODD_CSV.zip"
ODD_DEP_FILENAME = "ODD_DEP.csv"
SOCIO_SOURCE_LABEL = "INSEE - Indicateurs territoriaux de developpement durable (ODD_DEP)"
ALIGN_SOCIO_TO_ELECTION_YEARS = os.getenv("ALIGN_SOCIO_TO_ELECTION_YEARS", "true").lower() in {
    "1",
    "true",
    "yes",
}
ENRICH_GEO_FROM_ODD = os.getenv("ENRICH_GEO_FROM_ODD", "true").lower() in {
    "1",
    "true",
    "yes",
}
ENRICH_GEO_COORDS_FROM_GEO_API = os.getenv("ENRICH_GEO_COORDS_FROM_GEO_API", "true").lower() in {
    "1",
    "true",
    "yes",
}
USE_CIRC_CSV_FOR_ELECTION_COUNTS = os.getenv(
    "USE_CIRC_CSV_FOR_ELECTION_COUNTS", "true"
).lower() in {"1", "true", "yes"}
LOAD_COMMUNE_RESULTS = os.getenv("LOAD_COMMUNE_RESULTS", "false").lower() in {"1", "true", "yes"}
LOAD_MUNICIPAL_RESULTS = os.getenv("LOAD_MUNICIPAL_RESULTS", "false").lower() in {
    "1",
    "true",
    "yes",
}
MUNICIPAL_RESULTS_CSV_PATH = os.getenv(
    "MUNICIPAL_RESULTS_CSV_PATH",
    "data/raw/external/municipales_commune.csv",
)

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
    {
        "indicator_code": "unemployment_rate_youth_15_24",
        "indicator_name": "Taux de chomage BIT 15-24 ans",
        "unit": "%",
        "variable": "taux_chom_bit",
        "sous_champ": "15_24",
    },
    {
        "indicator_code": "unemployment_rate_women",
        "indicator_name": "Taux de chomage BIT femmes",
        "unit": "%",
        "variable": "taux_chom_bit",
        "sous_champ": "femme",
    },
    {
        "indicator_code": "unemployment_rate_men",
        "indicator_name": "Taux de chomage BIT hommes",
        "unit": "%",
        "variable": "taux_chom_bit",
        "sous_champ": "homme",
    },
    {
        "indicator_code": "life_expectancy_women",
        "indicator_name": "Esperance de vie des femmes",
        "unit": "annees",
        "variable": "esper_vie",
        "sous_champ": "femme",
    },
    {
        "indicator_code": "life_expectancy_men",
        "indicator_name": "Esperance de vie des hommes",
        "unit": "annees",
        "variable": "esper_vie",
        "sous_champ": "homme",
    },
    {
        "indicator_code": "long_term_jobseekers_share",
        "indicator_name": "Part des demandeurs d'emploi de longue duree",
        "unit": "%",
        "variable": "part_deld",
        "sous_champ": None,
    },
    {
        "indicator_code": "jobseekers_de_count",
        "indicator_name": "Nombre de demandeurs d'emploi categories D/E",
        "unit": "nombre",
        "variable": "nb_deld",
        "sous_champ": None,
    },
    {
        "indicator_code": "jobseekers_abc_count",
        "indicator_name": "Nombre de demandeurs d'emploi categories A/B/C",
        "unit": "nombre",
        "variable": "nb_deABC",
        "sous_champ": None,
    },
    {
        "indicator_code": "overindebtedness_cases_count",
        "indicator_name": "Nombre de dossiers de surendettement deposes",
        "unit": "nombre",
        "variable": "nb_dossiers_deposes",
        "sous_champ": None,
    },
    {
        "indicator_code": "population_total",
        "indicator_name": "Population totale",
        "unit": "habitants",
        "variable": "pop",
        "sous_champ": None,
    },
    {
        "indicator_code": "establishments_count",
        "indicator_name": "Nombre d'etablissements",
        "unit": "nombre",
        "variable": "nb_etablissements",
        "sous_champ": None,
    },
    {
        "indicator_code": "business_creations_count",
        "indicator_name": "Nombre de creations d'etablissements",
        "unit": "nombre",
        "variable": "nb_crea_etablissements",
        "sous_champ": None,
    },
    {
        "indicator_code": "business_creation_rate",
        "indicator_name": "Taux de creations d'etablissements",
        "unit": "%",
        "variable": "taux_crea_etab",
        "sous_champ": None,
    },
    {
        "indicator_code": "declared_income_median",
        "indicator_name": "Revenu declare median",
        "unit": "EUR",
        "variable": "revenu_decl_median",
        "sous_champ": None,
    },
    {
        "indicator_code": "taxable_households_share",
        "indicator_name": "Part des foyers fiscaux imposes",
        "unit": "%",
        "variable": "part_foy_fisc_impos",
        "sous_champ": None,
    },
    {
        "indicator_code": "social_benefits_income_share",
        "indicator_name": "Poids des prestations sociales dans le revenu disponible",
        "unit": "%",
        "variable": "poids_presta_sociale_revenu_dispo",
        "sous_champ": None,
    },
    {
        "indicator_code": "school_leavers_20_24_count",
        "indicator_name": "Nombre de 20-24 ans sortis d'etudes",
        "unit": "nombre",
        "variable": "20_24_sortis_etudes",
        "sous_champ": None,
    },
    {
        "indicator_code": "school_leavers_20_24_no_diploma_count",
        "indicator_name": "Nombre de 20-24 ans sortis d'etudes sans diplome",
        "unit": "nombre",
        "variable": "20_24_sortis_etudes_nondip",
        "sous_champ": None,
    },
    {
        "indicator_code": "population_age_75_plus_count",
        "indicator_name": "Population de 75 ans ou plus",
        "unit": "habitants",
        "variable": "pop75",
        "sous_champ": None,
    },
    {
        "indicator_code": "population_age_75_plus_share",
        "indicator_name": "Part de la population de 75 ans ou plus",
        "unit": "%",
        "variable": "part_pop75",
        "sous_champ": None,
    },
    {
        "indicator_code": "catnat_communes_flood_count",
        "indicator_name": "Communes reconnues CatNat - inondations",
        "unit": "nombre",
        "variable": "nb_com_catnat",
        "sous_champ": "ino",
    },
    {
        "indicator_code": "catnat_communes_storm_count",
        "indicator_name": "Communes reconnues CatNat - tempetes",
        "unit": "nombre",
        "variable": "nb_com_catnat",
        "sous_champ": "atm",
    },
    {
        "indicator_code": "catnat_communes_drought_count",
        "indicator_name": "Communes reconnues CatNat - secheresse",
        "unit": "nombre",
        "variable": "nb_com_catnat",
        "sous_champ": "sec",
    },
]

CACHE_DIR = Path("data/raw/data_gouv_cache")

METADATA_COLUMNS_NORMALIZED = {
    "departement",
    "codedepartement",
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
    "blancsetnuls",
    "exprimes",
    "exp",
    "etatsaisie",
    "deptcode",
    "deptname",
}

CIRC_CSV_METADATA_COLUMNS_NORMALIZED = METADATA_COLUMNS_NORMALIZED | {
    "circonscription",
    "codedelacirconscription",
    "codedelacirconscriptionlegislative",
}

DEFAULT_PARTY_CODE = "NR"
DEFAULT_PARTY_NAME = "Non renseigne"

# Reference table to populate candidate.party_code / candidate.party_name.
# The list covers candidates present in the loaded 1969-2022 first-round dataset.
CANDIDATE_PARTY_REFERENCE = {
    "ARTHAUD": ("LO", "Lutte Ouvriere"),
    "ASSELINEAU": ("UPR", "Union Populaire Republicaine"),
    "BALLADUR": ("RPR", "Rassemblement pour la Republique"),
    "BARRE": ("UDF", "Union pour la Democratie Francaise"),
    "BAYROU": ("MODEM", "Mouvement Democrate"),
    "BESANCENOT": ("LCR", "Ligue Communiste Revolutionnaire"),
    "BOUCHARDEAU": ("PSU", "Parti Socialiste Unifie"),
    "BOUSSEL": ("PT", "Parti des Travailleurs"),
    "BOUTIN": ("FRS", "Forum des Republicains Sociaux"),
    "BOVE": ("ALT", "Altermondialiste"),
    "BUFFET": ("PCF", "Parti Communiste Francais"),
    "CHABAN-DELMAS": ("UDR", "Union des Democrates pour la Republique"),
    "CHEMINADE": ("SP", "Solidarite et Progres"),
    "CHEVENEMENT": ("MDC", "Mouvement des Citoyens"),
    "CHIRAC": ("RPR_UMP", "RPR puis UMP"),
    "CREPEAU": ("MRG", "Mouvement des Radicaux de Gauche"),
    "DEBRE": ("RPR", "Rassemblement pour la Republique"),
    "DEFFERRE": ("FGDS", "Federation de la Gauche Democrate et Socialiste"),
    "DUCATEL": ("DEMO", "Democratie"),
    "DUCLOS": ("PCF", "Parti Communiste Francais"),
    "DUMONT": ("ECO", "Ecologiste"),
    "DUPONT-AIGNAN": ("DLF", "Debout la France"),
    "FILLON": ("LR", "Les Republicains"),
    "GARAUD": ("RPR", "Rassemblement pour la Republique"),
    "GISCARD D'ESTAING": ("UDF", "Union pour la Democratie Francaise"),
    "GLUCKSTEIN": ("PT", "Parti des Travailleurs"),
    "HAMON": ("PS", "Parti Socialiste"),
    "HERAUD": ("REG", "Regionaliste"),
    "HIDALGO": ("PS", "Parti Socialiste"),
    "HOLLANDE": ("PS", "Parti Socialiste"),
    "HUE": ("PCF", "Parti Communiste Francais"),
    "JADOT": ("EELV", "Europe Ecologie Les Verts"),
    "JOLY": ("EELV", "Europe Ecologie Les Verts"),
    "JOSPIN": ("PS", "Parti Socialiste"),
    "JUQUIN": ("DVG", "Divers Gauche"),
    "KRIVINE": ("LCR", "Ligue Communiste Revolutionnaire"),
    "LAGUILLER": ("LO", "Lutte Ouvriere"),
    "LAJOINIE": ("PCF", "Parti Communiste Francais"),
    "LALONDE": ("ECO", "Ecologiste"),
    "LASSALLE": ("RES", "Resistons"),
    "LEPAGE": ("CAP21", "Cap21"),
    "LE PEN": ("FN_RN", "Front National puis Rassemblement National"),
    "MACRON": ("LREM_RE", "La Republique En Marche puis Renaissance"),
    "MADELIN": ("DL", "Democratie Liberale"),
    "MAMERE": ("LV", "Les Verts"),
    "MARCHAIS": ("PCF", "Parti Communiste Francais"),
    "MEGRET": ("MNR", "Mouvement National Republicain"),
    "MELENCHON": ("LFI", "La France Insoumise"),
    "MITTERRAND": ("PS", "Parti Socialiste"),
    "MULLER": ("PSD", "Parti Social Democrate"),
    "NIHOUS": ("CPNT", "Chasse Peche Nature et Traditions"),
    "PECRESSE": ("LR", "Les Republicains"),
    "POHER": ("CD", "Centre Democrate"),
    "POMPIDOU": ("UDR", "Union des Democrates pour la Republique"),
    "POUTOU": ("NPA", "Nouveau Parti Anticapitaliste"),
    "RENOUVIN": ("NAR", "Nouvelle Action Royaliste"),
    "ROCARD": ("PSU", "Parti Socialiste Unifie"),
    "ROUSSEL": ("PCF", "Parti Communiste Francais"),
    "ROYAL": ("PS", "Parti Socialiste"),
    "ROYER": ("CNIP", "Centre National des Independants et Paysans"),
    "SAINT-JOSSE": ("CPNT", "Chasse Peche Nature et Traditions"),
    "SARKOZY": ("UMP", "Union pour un Mouvement Populaire"),
    "SCHIVARDI": ("PT", "Parti des Travailleurs"),
    "SEBAG": ("LO", "Lutte Ouvriere"),
    "TAUBIRA": ("PRG", "Parti Radical de Gauche"),
    "VILLIERS": ("MPF", "Mouvement pour la France"),
    "VOYNET": ("LV", "Les Verts"),
    "WAECHTER": ("LV", "Les Verts"),
    "ZEMMOUR": ("REC", "Reconquete"),
}


def _party_reference_for_candidate(candidate_name):
    normalized_name = str(candidate_name or "").strip().upper()
    if not normalized_name:
        return (DEFAULT_PARTY_CODE, DEFAULT_PARTY_NAME)
    return CANDIDATE_PARTY_REFERENCE.get(
        normalized_name,
        (DEFAULT_PARTY_CODE, DEFAULT_PARTY_NAME),
    )


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


def _read_json_url(url):
    with urllib.request.urlopen(url, timeout=30) as response:
        raw = response.read()
    return json.loads(raw.decode("utf-8"))


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


def _normalize_commune_code(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    if not text:
        return None
    text = re.sub(r"[^0-9]", "", text)
    if not text:
        return None
    return text.zfill(3)[-3:]


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


def _canonical_candidate_name_from_circ_column(value):
    text = "" if value is None else str(value)
    text = text.replace("’", "'")

    # Remove a standard trailing party tag, e.g. "(PS)", "(FN)".
    text = re.sub(r"\s*\([^)]*\)\s*$", "", text).strip()
    # Handle malformed trailing labels like "DE VILLIERS MPF)".
    text = re.sub(r"\s+[A-Z]{2,6}\)$", "", text).strip()

    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return ""

    tokens = []
    for token in text.split(" "):
        clean_token = re.sub(r"[^A-Za-z'-]", "", token)
        if not clean_token:
            continue
        if clean_token == clean_token.upper() and any(ch.isalpha() for ch in clean_token):
            tokens.append(clean_token)

    name = " ".join(tokens).upper() if tokens else text.upper()

    if name == "DE VILLIERS":
        return "VILLIERS"
    return name


def _read_csv_with_encoding_fallback(local_path):
    last_error = None
    for encoding in ("utf-8-sig", "latin-1"):
        try:
            head = local_path.read_text(encoding=encoding, errors="strict").splitlines()[0]
            delimiter = ";" if head.count(";") > head.count(",") else ","
            return pd.read_csv(local_path, sep=delimiter, encoding=encoding, low_memory=False)
        except UnicodeDecodeError as exc:
            last_error = exc
            continue

    raise RuntimeError(f"Could not decode CSV file {local_path.name}: {last_error}")


def _read_text_with_encoding_fallback(local_path):
    last_error = None
    for encoding in ("utf-8-sig", "latin-1"):
        try:
            return local_path.read_text(encoding=encoding, errors="strict")
        except UnicodeDecodeError as exc:
            last_error = exc
            continue

    raise RuntimeError(f"Could not decode text file {local_path.name}: {last_error}")


def _read_first_round_circ_csv_by_department(year, url):
    print(f"[extract] year={year} source=csv_circ")
    local_path = _cached_download(url)
    df = _read_csv_with_encoding_fallback(local_path)
    df.columns = [str(c).strip() for c in df.columns]

    dept_code_col = _first_matching_column(df.columns, {"codedepartement", "codedudepartement"})
    dept_name_col = _first_matching_column(df.columns, {"departement", "libelledudepartement"})
    registered_col = _first_matching_column(df.columns, {"inscrits", "ins"})
    votes_cast_col = _first_matching_column(df.columns, {"votants"})
    votes_valid_col = _first_matching_column(df.columns, {"exprimes", "exp"})

    if not dept_code_col or not dept_name_col:
        raise RuntimeError(f"Missing department columns in circ CSV for year {year}.")
    if not registered_col or not votes_cast_col or not votes_valid_col:
        raise RuntimeError(f"Missing election volume columns in circ CSV for year {year}.")

    df["dept_code"] = df[dept_code_col].map(_normalize_dept_code)
    df["dept_name"] = df[dept_name_col].astype(str).str.strip()
    df = df[df["dept_code"].isin(TARGET_DEPT_CODES)].copy()
    if df.empty:
        return pd.DataFrame(columns=_result_columns())

    candidate_columns = []
    for col in df.columns:
        normalized = _normalize_text(col)
        if normalized in CIRC_CSV_METADATA_COLUMNS_NORMALIZED:
            continue
        if col in {"dept_code", "dept_name"}:
            continue
        if pd.to_numeric(df[col], errors="coerce").notna().sum() == 0:
            continue
        candidate_columns.append(col)

    if not candidate_columns:
        raise RuntimeError(f"No candidate vote columns detected in circ CSV for year {year}.")

    def _sum_int(series):
        value = pd.to_numeric(series, errors="coerce").sum(min_count=1)
        if pd.isna(value):
            return None
        return int(round(float(value)))

    records = []
    for dept_code, dept_df in df.groupby("dept_code"):
        dept_name = dept_df["dept_name"].iloc[0] if "dept_name" in dept_df.columns else dept_code
        registered = _sum_int(dept_df[registered_col])
        votes_cast = _sum_int(dept_df[votes_cast_col])
        votes_valid = _sum_int(dept_df[votes_valid_col])

        turnout_rate = None
        if registered and votes_cast is not None and registered != 0:
            turnout_rate = round(votes_cast / registered, 6)

        for candidate_col in candidate_columns:
            candidate_name = _canonical_candidate_name_from_circ_column(candidate_col)
            if not candidate_name:
                continue

            votes = _sum_int(dept_df[candidate_col])
            if votes is None:
                continue

            vote_share = None
            if votes_valid:
                vote_share = round(votes / votes_valid, 6)
            if vote_share is None:
                continue

            records.append(
                {
                    "year": year,
                    "dept_code": dept_code,
                    "dept_name": dept_name or IDF_DEPARTMENTS.get(dept_code, dept_code),
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

    result = (
        result.sort_values(["year", "dept_code", "candidate_name"])
        .groupby(["year", "dept_code", "dept_name", "candidate_name"], as_index=False)
        .agg(
            registered=("registered", "max"),
            votes_cast=("votes_cast", "max"),
            votes_valid=("votes_valid", "max"),
            votes=("votes", "sum"),
            vote_share=("vote_share", "max"),
            turnout_rate=("turnout_rate", "max"),
        )
    )
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


def _commune_result_columns():
    return [
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


def _read_first_round_commp9000_csv_to_commune(year, url):
    print(f"[extract] year={year} source=csv_commp9000")
    local_path = _cached_download(url)
    content = _read_text_with_encoding_fallback(local_path)

    reader = csv.reader(io.StringIO(content), delimiter=",")
    header = next(reader, None)
    second_row = next(reader, None)
    if not header or not second_row:
        return pd.DataFrame(columns=_commune_result_columns())

    header = [str(cell).strip() for cell in header]
    second_row = [str(cell).strip() for cell in second_row]
    normalized_header = [_normalize_text(cell) for cell in header]

    def _find_idx(names):
        for idx, name in enumerate(normalized_header):
            if name in names:
                return idx
        return None

    dept_code_idx = _find_idx({"codedepartement", "codedudepartement"})
    commune_code_idx = _find_idx({"numerocommune", "numerodecommune", "codedelacommune"})
    commune_name_idx = _find_idx({"commune", "nomdelacommune", "libelledelacommune"})
    registered_idx = _find_idx({"inscrits", "ins"})
    votes_cast_idx = _find_idx({"votants"})
    votes_valid_idx = _find_idx({"exprimes", "exp"})
    abstentions_idx = _find_idx({"abstentions"})

    required_idxs = [dept_code_idx, commune_code_idx, registered_idx, votes_valid_idx]
    if any(idx is None for idx in required_idxs):
        raise RuntimeError(f"Unexpected commp9000 CSV format for year {year}.")

    metadata_names = {
        "codedepartement",
        "codedudepartement",
        "departement",
        "numerocommune",
        "numerodecommune",
        "codedelacommune",
        "commune",
        "nomdelacommune",
        "libelledelacommune",
        "population",
        "inscrits",
        "ins",
        "abstentions",
        "votants",
        "exprimes",
        "exp",
        "blancs",
        "nuls",
        "blancsetnuls",
    }

    second_normalized = [_normalize_text(cell) for cell in second_row]
    has_subheader = any("voixcandidat" in cell for cell in second_normalized)

    candidate_columns = []
    for idx, raw_name in enumerate(header):
        if idx >= len(second_normalized):
            continue
        if not raw_name:
            continue
        normalized = normalized_header[idx]
        if normalized in metadata_names:
            continue
        if has_subheader and not second_normalized[idx].startswith("voixcandidat"):
            continue

        candidate_name = _canonical_candidate_name_from_circ_column(raw_name)
        if candidate_name:
            candidate_columns.append((idx, candidate_name))

    if not candidate_columns:
        raise RuntimeError(f"No candidate vote columns detected in commp9000 CSV for year {year}.")

    data_rows = list(reader) if has_subheader else [second_row] + list(reader)

    records = []
    for row in data_rows:
        if not row or all(str(cell).strip() == "" for cell in row):
            continue
        if len(row) <= max(required_idxs):
            continue

        dept_code = _normalize_dept_code(row[dept_code_idx])
        if dept_code not in TARGET_DEPT_CODES:
            continue

        commune_code = _normalize_commune_code(row[commune_code_idx])
        if not commune_code:
            continue
        insee_code = f"{dept_code}{commune_code}"

        commune_name = insee_code
        if commune_name_idx is not None and commune_name_idx < len(row):
            commune_name = str(row[commune_name_idx]).strip() or insee_code

        registered = _to_int(row[registered_idx]) if registered_idx is not None else None
        votes_cast = _to_int(row[votes_cast_idx]) if votes_cast_idx is not None and votes_cast_idx < len(row) else None
        votes_valid = _to_int(row[votes_valid_idx]) if votes_valid_idx is not None else None

        if votes_cast is None and abstentions_idx is not None and abstentions_idx < len(row):
            abstentions = _to_int(row[abstentions_idx])
            if abstentions is not None and registered is not None:
                votes_cast = max(int(registered) - int(abstentions), 0)

        turnout_rate = None
        if registered and votes_cast is not None and registered != 0:
            turnout_rate = round(votes_cast / registered, 6)

        for vote_idx, candidate_name in candidate_columns:
            if vote_idx >= len(row):
                continue
            votes = _to_int(row[vote_idx])
            if votes is None:
                continue

            vote_share = None
            if votes_valid:
                vote_share = round(votes / votes_valid, 6)

            records.append(
                {
                    "year": int(year),
                    "insee_code": insee_code,
                    "commune_name": commune_name,
                    "dept_code": dept_code,
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
        return pd.DataFrame(columns=_commune_result_columns())
    return result[_commune_result_columns()]


def _read_2012_first_round_from_bureau_txt_to_commune(url):
    print("[extract] year=2012 source=txt_bureaux")
    local_path = _cached_download(url)
    content = local_path.read_text(encoding="latin-1", errors="replace")
    reader = csv.reader(io.StringIO(content), delimiter=";")

    seen_bureaus = set()
    totals_by_commune = {}
    candidate_votes = {}

    for row in reader:
        if len(row) < 15:
            continue

        round_no = row[0].strip()
        if round_no != "1":
            continue

        dept_code = _normalize_dept_code(row[1])
        if dept_code not in TARGET_DEPT_CODES:
            continue

        commune_code = _normalize_commune_code(row[2])
        if not commune_code:
            continue
        insee_code = f"{dept_code}{commune_code}"
        commune_name = row[3].strip() or insee_code
        bureau_code = row[6].strip() or "0000"
        bureau_key = (insee_code, bureau_code)

        if bureau_key not in seen_bureaus:
            seen_bureaus.add(bureau_key)
            registered = _to_int(row[7]) or 0
            votes_cast = _to_int(row[8]) or 0
            votes_valid = _to_int(row[9]) or 0
            current = totals_by_commune.setdefault(
                insee_code,
                {
                    "commune_name": commune_name,
                    "dept_code": dept_code,
                    "registered": 0,
                    "votes_cast": 0,
                    "votes_valid": 0,
                },
            )
            current["registered"] += registered
            current["votes_cast"] += votes_cast
            current["votes_valid"] += votes_valid

        candidate_name = _canonical_candidate_name(row[11].strip())
        votes = _to_int(row[14]) or 0
        key = (insee_code, candidate_name)
        candidate_votes[key] = candidate_votes.get(key, 0) + votes

    records = []
    for (insee_code, candidate_name), votes in candidate_votes.items():
        totals = totals_by_commune.get(insee_code, {})
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
                "year": 2012,
                "insee_code": insee_code,
                "commune_name": totals.get("commune_name", insee_code),
                "dept_code": totals.get("dept_code"),
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
        return pd.DataFrame(columns=_commune_result_columns())
    return result[_commune_result_columns()]


def _read_2007_first_round_from_bureau_txt_to_commune(url):
    print("[extract] year=2007 source=txt_bureaux")
    local_path = _cached_download(url)
    content = local_path.read_text(encoding="latin-1", errors="replace")
    reader = csv.reader(io.StringIO(content), delimiter=";")

    seen_bureaus = set()
    totals_by_commune = {}
    candidate_votes = {}

    for row in reader:
        if not row:
            continue
        first_cell = str(row[0]).strip()
        if not first_cell or first_cell.startswith("--"):
            continue
        if len(row) < 13:
            continue

        round_no = first_cell
        if round_no != "1":
            continue

        dept_code = _normalize_dept_code(row[1])
        if dept_code not in TARGET_DEPT_CODES:
            continue

        commune_code = _normalize_commune_code(row[2])
        if not commune_code:
            continue
        insee_code = f"{dept_code}{commune_code}"
        commune_name = str(row[3]).strip() or insee_code
        bureau_code = str(row[4]).strip() or "0000"
        bureau_key = (insee_code, bureau_code)

        if bureau_key not in seen_bureaus:
            seen_bureaus.add(bureau_key)
            registered = _to_int(row[5]) or 0
            votes_cast = _to_int(row[6]) or 0
            votes_valid = _to_int(row[7]) or 0
            current = totals_by_commune.setdefault(
                insee_code,
                {
                    "commune_name": commune_name,
                    "dept_code": dept_code,
                    "registered": 0,
                    "votes_cast": 0,
                    "votes_valid": 0,
                },
            )
            current["registered"] += registered
            current["votes_cast"] += votes_cast
            current["votes_valid"] += votes_valid

        candidate_last_name = str(row[9]).strip()
        candidate_first_name = str(row[10]).strip()
        candidate_raw = f"{candidate_last_name} {candidate_first_name}".strip()
        candidate_name = _canonical_candidate_name(candidate_raw)
        votes = _to_int(row[12]) or 0
        key = (insee_code, candidate_name)
        candidate_votes[key] = candidate_votes.get(key, 0) + votes

    records = []
    for (insee_code, candidate_name), votes in candidate_votes.items():
        totals = totals_by_commune.get(insee_code, {})
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
                "year": 2007,
                "insee_code": insee_code,
                "commune_name": totals.get("commune_name", insee_code),
                "dept_code": totals.get("dept_code"),
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
        return pd.DataFrame(columns=_commune_result_columns())
    return result[_commune_result_columns()]


def _read_first_round_bureau_txt_to_commune(year, url):
    print(f"[extract] year={year} source=txt_bureaux")
    local_path = _cached_download(url)
    content = local_path.read_text(encoding="latin-1", errors="replace")

    reader = csv.reader(io.StringIO(content), delimiter=";")
    header = next(reader, None)
    if not header:
        return pd.DataFrame(columns=_commune_result_columns())

    normalized_header = [_normalize_text(h) for h in header]
    idx_by_name = {name: i for i, name in enumerate(normalized_header)}

    required = [
        "codedudepartement",
        "codedelacommune",
        "libelledelacommune",
        "codedubvote",
        "inscrits",
        "votants",
        "exprimes",
        "npanneau",
    ]
    missing = [name for name in required if name not in idx_by_name]
    if missing:
        raise RuntimeError(f"Unexpected TXT format for year {year}, missing columns: {missing}")

    candidate_start = idx_by_name["npanneau"]
    chunk_size = 7

    seen_bureaus = set()
    totals_by_commune = {}
    candidate_votes = {}

    for row in reader:
        if len(row) <= candidate_start:
            continue

        dept_code = _normalize_dept_code(row[idx_by_name["codedudepartement"]])
        if dept_code not in TARGET_DEPT_CODES:
            continue

        commune_code = _normalize_commune_code(row[idx_by_name["codedelacommune"]])
        if not commune_code:
            continue
        insee_code = f"{dept_code}{commune_code}"
        commune_name = row[idx_by_name["libelledelacommune"]].strip() or insee_code
        bureau_code = row[idx_by_name["codedubvote"]].strip() or "0000"
        bureau_key = (insee_code, bureau_code)

        if bureau_key not in seen_bureaus:
            seen_bureaus.add(bureau_key)
            registered = _to_int(row[idx_by_name["inscrits"]]) or 0
            votes_cast = _to_int(row[idx_by_name["votants"]]) or 0
            votes_valid = _to_int(row[idx_by_name["exprimes"]]) or 0
            current = totals_by_commune.setdefault(
                insee_code,
                {
                    "commune_name": commune_name,
                    "dept_code": dept_code,
                    "registered": 0,
                    "votes_cast": 0,
                    "votes_valid": 0,
                },
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
            key = (insee_code, candidate_name)
            candidate_votes[key] = candidate_votes.get(key, 0) + votes

    records = []
    for (insee_code, candidate_name), votes in candidate_votes.items():
        totals = totals_by_commune.get(insee_code, {})
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
                "year": int(year),
                "insee_code": insee_code,
                "commune_name": totals.get("commune_name", insee_code),
                "dept_code": totals.get("dept_code"),
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
        return pd.DataFrame(columns=_commune_result_columns())
    return result[_commune_result_columns()]


def _collect_all_commune_results():
    all_records = []

    for year, url in sorted(FIRST_ROUND_COMMP9000_CSV_URL_BY_YEAR.items()):
        frame = _read_first_round_commp9000_csv_to_commune(int(year), url)
        if not frame.empty:
            all_records.extend(frame.to_dict(orient="records"))

    for year, url in sorted(COMMUNE_BUREAU_SOURCE_URL_BY_YEAR.items()):
        if int(year) == 2007:
            frame = _read_2007_first_round_from_bureau_txt_to_commune(url)
        elif int(year) == 2012:
            frame = _read_2012_first_round_from_bureau_txt_to_commune(url)
        else:
            frame = _read_first_round_bureau_txt_to_commune(int(year), url)
        if not frame.empty:
            all_records.extend(frame.to_dict(orient="records"))

    if not all_records:
        return pd.DataFrame(columns=_commune_result_columns())

    df = pd.DataFrame.from_records(all_records, columns=_commune_result_columns())
    if df.empty:
        return df

    df = (
        df.sort_values(["year", "insee_code", "candidate_name"])
        .groupby(["year", "insee_code", "commune_name", "dept_code", "candidate_name"], as_index=False)
        .agg(
            registered=("registered", "max"),
            votes_cast=("votes_cast", "max"),
            votes_valid=("votes_valid", "max"),
            votes=("votes", lambda s: s.sum(min_count=1)),
            vote_share=("vote_share", "max"),
            turnout_rate=("turnout_rate", "max"),
        )
    )

    df["votes"] = pd.to_numeric(df["votes"], errors="coerce")
    df["votes_valid"] = pd.to_numeric(df["votes_valid"], errors="coerce")
    df["vote_share"] = pd.to_numeric(df["vote_share"], errors="coerce")
    mask = df["votes"].notna() & df["votes_valid"].notna() & (df["votes_valid"] != 0)
    df.loc[mask, "vote_share"] = (df.loc[mask, "votes"] / df.loc[mask, "votes_valid"]).round(6)
    return df[_commune_result_columns()]


def _normalize_insee_code(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = re.sub(r"[^0-9]", "", str(value).strip())
    if not text:
        return None
    return text.zfill(5)[-5:]


def _read_municipal_commune_results_csv(csv_path):
    path = Path(csv_path)
    if not path.exists():
        print(f"[warn] municipal CSV not found: {path}")
        return pd.DataFrame(columns=_commune_result_columns())

    print(f"[extract] source=municipal_csv file={path}")
    df = _read_csv_with_encoding_fallback(path)
    if df.empty:
        return pd.DataFrame(columns=_commune_result_columns())

    df.columns = [str(c).strip() for c in df.columns]
    normalized_cols = {_normalize_text(c): c for c in df.columns}

    def _col(candidates):
        for name in candidates:
            if name in normalized_cols:
                return normalized_cols[name]
        return None

    year_col = _col({"year", "annee", "an"})
    insee_col = _col({"inseecode", "codeinsee", "codecommuneinsee", "codgeo", "codecommune"})
    commune_name_col = _col({"commune", "nomcommune", "libelledelacommune", "communename"})
    dept_code_col = _col({"codedepartement", "departement", "deptcode", "dept_code"})
    candidate_col = _col(
        {
            "candidatename",
            "candidat",
            "nomcandidat",
            "nomdeliste",
            "tetedeliste",
            "liste",
        }
    )
    votes_col = _col({"votes", "voix", "nbvoix", "voixobtenues"})
    votes_valid_col = _col({"votesvalid", "exprimes", "suffragesexprimes", "nbexprimes"})
    votes_cast_col = _col({"votescast", "votants", "nbvotants"})
    registered_col = _col({"registered", "inscrits", "nbinscrits"})
    vote_share_col = _col({"voteshare", "part", "pourcentage", "pct", "pourcvoix"})
    turnout_col = _col({"turnoutrate", "participation", "txparticipation"})

    required_missing = []
    if year_col is None:
        required_missing.append("year")
    if insee_col is None:
        required_missing.append("insee_code")
    if candidate_col is None:
        required_missing.append("candidate_name")
    if votes_col is None and vote_share_col is None:
        required_missing.append("votes or vote_share")
    if required_missing:
        print(
            "[warn] municipal CSV missing required columns: "
            + ", ".join(required_missing)
        )
        return pd.DataFrame(columns=_commune_result_columns())

    records = []
    for _, row in df.iterrows():
        year = _to_int(row.get(year_col))
        if year is None:
            continue

        insee_code = _normalize_insee_code(row.get(insee_col))
        if not insee_code or len(insee_code) != 5:
            continue
        dept_code = _normalize_dept_code(row.get(dept_code_col)) if dept_code_col else insee_code[:2]
        if dept_code not in TARGET_DEPT_CODES:
            continue

        candidate_name = _canonical_candidate_name(row.get(candidate_col))
        if not candidate_name:
            continue

        votes = _to_int(row.get(votes_col)) if votes_col else None
        votes_valid = _to_int(row.get(votes_valid_col)) if votes_valid_col else None
        votes_cast = _to_int(row.get(votes_cast_col)) if votes_cast_col else None
        registered = _to_int(row.get(registered_col)) if registered_col else None

        vote_share = None
        if vote_share_col:
            vote_share = _to_float(row.get(vote_share_col))
            if vote_share is not None and vote_share > 1.0:
                vote_share = vote_share / 100.0
        if vote_share is None and votes is not None and votes_valid:
            vote_share = round(votes / votes_valid, 6)
        if votes is None and vote_share is not None and votes_valid:
            votes = int(round(votes_valid * vote_share))

        turnout_rate = None
        if turnout_col:
            turnout_rate = _to_float(row.get(turnout_col))
            if turnout_rate is not None and turnout_rate > 1.0:
                turnout_rate = turnout_rate / 100.0
        if turnout_rate is None and registered and votes_cast is not None and registered != 0:
            turnout_rate = round(votes_cast / registered, 6)

        if vote_share is None:
            continue

        commune_name = (
            str(row.get(commune_name_col)).strip()
            if commune_name_col
            else insee_code
        )
        if not commune_name:
            commune_name = insee_code

        records.append(
            {
                "year": int(year),
                "insee_code": insee_code,
                "commune_name": commune_name,
                "dept_code": dept_code,
                "candidate_name": candidate_name,
                "registered": registered,
                "votes_cast": votes_cast,
                "votes_valid": votes_valid,
                "votes": votes,
                "vote_share": float(vote_share),
                "turnout_rate": turnout_rate,
            }
        )

    out = pd.DataFrame.from_records(records, columns=_commune_result_columns())
    if out.empty:
        return out

    out = (
        out.sort_values(["year", "insee_code", "candidate_name"])
        .groupby(["year", "insee_code", "commune_name", "dept_code", "candidate_name"], as_index=False)
        .agg(
            registered=("registered", "max"),
            votes_cast=("votes_cast", "max"),
            votes_valid=("votes_valid", "max"),
            votes=("votes", lambda s: s.sum(min_count=1)),
            vote_share=("vote_share", "max"),
            turnout_rate=("turnout_rate", "max"),
        )
    )

    out["votes"] = pd.to_numeric(out["votes"], errors="coerce")
    out["votes_valid"] = pd.to_numeric(out["votes_valid"], errors="coerce")
    out["vote_share"] = pd.to_numeric(out["vote_share"], errors="coerce")
    mask = out["votes"].notna() & out["votes_valid"].notna() & (out["votes_valid"] != 0)
    out.loc[mask, "vote_share"] = (out.loc[mask, "votes"] / out.loc[mask, "votes_valid"]).round(6)
    return out[_commune_result_columns()]


def _collect_municipal_commune_results():
    return _read_municipal_commune_results_csv(MUNICIPAL_RESULTS_CSV_PATH)


def _collect_all_results():
    all_records = []
    loaded_years = set()

    if USE_CIRC_CSV_FOR_ELECTION_COUNTS:
        for year, url in sorted(FIRST_ROUND_CIRC_CSV_URL_BY_YEAR.items()):
            try:
                frame = _read_first_round_circ_csv_by_department(year, url)
            except Exception as exc:
                print(f"[warn] circ CSV extraction failed for year={year}, fallback to xlsx: {exc}")
                continue
            if frame.empty:
                continue
            loaded_years.add(year)
            all_records.extend(frame.to_dict(orient="records"))

    for year, url in sorted(FIRST_ROUND_XLSX_URL_BY_YEAR.items()):
        if year in loaded_years:
            continue
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


def _latest_odd_value_by_dept(odd_dep_df, variable, sous_champ=None):
    if odd_dep_df.empty:
        return {}

    year_columns = sorted(
        [col for col in odd_dep_df.columns if re.fullmatch(r"A\d{4}", str(col))],
        key=lambda col: int(col[1:]),
    )
    if not year_columns:
        return {}

    mask = odd_dep_df["variable"].astype(str) == str(variable)
    if sous_champ is None:
        mask &= odd_dep_df["sous_champ"].isna()
    else:
        mask &= odd_dep_df["sous_champ"].fillna("").astype(str).str.strip() == str(sous_champ)

    subset = odd_dep_df[mask].copy()
    if subset.empty:
        return {}

    out = {}
    for row in subset.itertuples(index=False):
        dept_code = _normalize_dept_code(getattr(row, "codgeo", None))
        if dept_code not in TARGET_DEPT_CODES:
            continue

        latest_value = None
        latest_year = None
        for year_col in reversed(year_columns):
            value = _to_float(getattr(row, year_col))
            if value is None:
                continue
            latest_value = float(value)
            latest_year = int(year_col[1:])
            break

        if latest_value is not None:
            out[dept_code] = (latest_value, latest_year)
    return out


def _collect_geo_enrichment_from_odd():
    if not ENRICH_GEO_FROM_ODD:
        return []

    odd_dep_df = _read_odd_dep_dataframe()
    if odd_dep_df.empty:
        return []

    population_by_dept = _latest_odd_value_by_dept(odd_dep_df, "pop", None)
    area_by_dept = _latest_odd_value_by_dept(odd_dep_df, "surfcom", None)

    rows = []
    for dept_code in TARGET_DEPT_CODES:
        if dept_code not in IDF_DEPARTMENTS:
            continue

        pop_raw, pop_year = population_by_dept.get(dept_code, (None, None))
        area_raw, area_year = area_by_dept.get(dept_code, (None, None))

        population = int(round(pop_raw)) if pop_raw is not None else None
        area_km2 = round(area_raw / 1_000_000.0, 6) if area_raw is not None else None

        if population is None and area_km2 is None:
            continue

        rows.append(
            {
                "insee_code": f"{dept_code}000",
                "commune_name": f"{IDF_DEPARTMENTS[dept_code]} (departement)",
                "dept_code": dept_code,
                "population": population,
                "area_km2": area_km2,
                "population_year": pop_year,
                "area_year": area_year,
            }
        )

    return rows


def _collect_dept_geo_coordinates_from_geo_api():
    if not ENRICH_GEO_COORDS_FROM_GEO_API:
        return []

    rows = []
    for dept_code in TARGET_DEPT_CODES:
        if dept_code not in IDF_DEPARTMENTS:
            continue

        try:
            dept_payload = _read_json_url(
                f"https://geo.api.gouv.fr/departements/{dept_code}?fields=code,nom,chefLieu"
            )
            chef_lieu_code = dept_payload.get("chefLieu")
            if not chef_lieu_code:
                print(f"[warn] no chefLieu found on geo.api for dept={dept_code}.")
                continue

            commune_payload = _read_json_url(
                "https://geo.api.gouv.fr/communes/"
                f"{chef_lieu_code}?fields=code,nom,centre&format=json&geometry=centre"
            )
            centre = commune_payload.get("centre") or {}
            coordinates = centre.get("coordinates")
            if not isinstance(coordinates, (list, tuple)) or len(coordinates) != 2:
                print(f"[warn] no centre coordinates found for commune={chef_lieu_code}.")
                continue

            longitude = _to_float(coordinates[0])
            latitude = _to_float(coordinates[1])
            if latitude is None or longitude is None:
                print(f"[warn] invalid centre coordinates for commune={chef_lieu_code}.")
                continue
        except Exception as exc:
            print(f"[warn] geo coordinates skipped for dept={dept_code}: {exc}")
            continue

        rows.append(
            {
                "insee_code": f"{dept_code}000",
                "commune_name": f"{IDF_DEPARTMENTS[dept_code]} (departement)",
                "dept_code": dept_code,
                "latitude": latitude,
                "longitude": longitude,
            }
        )

    return rows


def _collect_commune_geo_enrichment_from_geo_api(target_insee_codes=None):
    if not ENRICH_GEO_COORDS_FROM_GEO_API:
        return []

    target_codes = {
        str(code).strip()
        for code in (target_insee_codes or [])
        if str(code).strip()
    }

    rows = []
    for dept_code in TARGET_DEPT_CODES:
        if dept_code not in IDF_DEPARTMENTS:
            continue

        try:
            payload = _read_json_url(
                "https://geo.api.gouv.fr/communes"
                f"?codeDepartement={dept_code}"
                "&fields=code,nom,population,surface,centre"
                "&format=json&geometry=centre"
            )
        except Exception as exc:
            print(f"[warn] commune geo enrichment skipped for dept={dept_code}: {exc}")
            continue

        if not isinstance(payload, list):
            continue

        for item in payload:
            insee_code = str(item.get("code") or "").strip()
            if len(insee_code) != 5:
                continue
            if target_codes and insee_code not in target_codes:
                continue

            population = _to_int(item.get("population"))
            surface_ha = _to_float(item.get("surface"))
            area_km2 = round(surface_ha / 100.0, 6) if surface_ha is not None else None

            latitude = None
            longitude = None
            centre = item.get("centre") or {}
            coordinates = centre.get("coordinates")
            if isinstance(coordinates, (list, tuple)) and len(coordinates) == 2:
                longitude = _to_float(coordinates[0])
                latitude = _to_float(coordinates[1])

            rows.append(
                {
                    "insee_code": insee_code,
                    "commune_name": str(item.get("nom") or insee_code).strip() or insee_code,
                    "dept_code": insee_code[:2],
                    "population": population,
                    "area_km2": area_km2,
                    "latitude": latitude,
                    "longitude": longitude,
                }
            )

    return rows


def _collect_geo_enrichment_rows(target_insee_codes=None):
    rows_by_insee = {}
    for dept_code in TARGET_DEPT_CODES:
        if dept_code not in IDF_DEPARTMENTS:
            continue
        rows_by_insee[f"{dept_code}000"] = {
            "insee_code": f"{dept_code}000",
            "commune_name": f"{IDF_DEPARTMENTS[dept_code]} (departement)",
            "dept_code": dept_code,
            "population": None,
            "area_km2": None,
            "latitude": None,
            "longitude": None,
        }

    if ENRICH_GEO_FROM_ODD:
        odd_rows = _collect_geo_enrichment_from_odd()
        for row in odd_rows:
            target = rows_by_insee.setdefault(
                row["insee_code"],
                {
                    "insee_code": row["insee_code"],
                    "commune_name": row["commune_name"],
                    "dept_code": row["dept_code"],
                    "population": None,
                    "area_km2": None,
                    "latitude": None,
                    "longitude": None,
                },
            )
            if row.get("population") is not None:
                target["population"] = row["population"]
            if row.get("area_km2") is not None:
                target["area_km2"] = row["area_km2"]

    if ENRICH_GEO_COORDS_FROM_GEO_API:
        coord_rows = _collect_dept_geo_coordinates_from_geo_api()
        for row in coord_rows:
            target = rows_by_insee.setdefault(
                row["insee_code"],
                {
                    "insee_code": row["insee_code"],
                    "commune_name": row["commune_name"],
                    "dept_code": row["dept_code"],
                    "population": None,
                    "area_km2": None,
                    "latitude": None,
                    "longitude": None,
                },
            )
            if row.get("latitude") is not None:
                target["latitude"] = row["latitude"]
            if row.get("longitude") is not None:
                target["longitude"] = row["longitude"]

        commune_rows = _collect_commune_geo_enrichment_from_geo_api(
            target_insee_codes=target_insee_codes
        )
        for row in commune_rows:
            target = rows_by_insee.setdefault(
                row["insee_code"],
                {
                    "insee_code": row["insee_code"],
                    "commune_name": row["commune_name"],
                    "dept_code": row["dept_code"],
                    "population": None,
                    "area_km2": None,
                    "latitude": None,
                    "longitude": None,
                },
            )
            target["commune_name"] = row.get("commune_name", target.get("commune_name"))
            target["dept_code"] = row.get("dept_code", target.get("dept_code"))
            if row.get("population") is not None:
                target["population"] = row["population"]
            if row.get("area_km2") is not None:
                target["area_km2"] = row["area_km2"]
            if row.get("latitude") is not None:
                target["latitude"] = row["latitude"]
            if row.get("longitude") is not None:
                target["longitude"] = row["longitude"]

    rows = [
        row
        for row in rows_by_insee.values()
        if row["population"] is not None
        or row["area_km2"] is not None
        or row["latitude"] is not None
        or row["longitude"] is not None
    ]
    return rows


def _load_geo_enrichment(cur, target_insee_codes=None):
    if not ENRICH_GEO_FROM_ODD and not ENRICH_GEO_COORDS_FROM_GEO_API:
        return

    try:
        rows = _collect_geo_enrichment_rows(target_insee_codes=target_insee_codes)
    except Exception as exc:
        print(f"[warn] geo enrichment skipped: {exc}")
        return

    if not rows:
        print("[warn] no geo enrichment rows found.")
        return

    payload = [
        (
            row["insee_code"],
            row["commune_name"],
            row["dept_code"],
            row["population"],
            row["area_km2"],
            row["latitude"],
            row["longitude"],
        )
        for row in rows
    ]

    cur.executemany(
        """
        INSERT INTO geo_commune (
            insee_code,
            commune_name,
            dept_code,
            population,
            area_km2,
            latitude,
            longitude
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (insee_code) DO UPDATE
        SET commune_name = EXCLUDED.commune_name,
            dept_code = EXCLUDED.dept_code,
            population = COALESCE(EXCLUDED.population, geo_commune.population),
            area_km2 = COALESCE(EXCLUDED.area_km2, geo_commune.area_km2),
            latitude = COALESCE(EXCLUDED.latitude, geo_commune.latitude),
            longitude = COALESCE(EXCLUDED.longitude, geo_commune.longitude)
        """,
        payload,
    )

    pop_count = sum(1 for row in rows if row["population"] is not None)
    area_count = sum(1 for row in rows if row["area_km2"] is not None)
    lat_count = sum(1 for row in rows if row["latitude"] is not None)
    lon_count = sum(1 for row in rows if row["longitude"] is not None)
    print(
        f"[load] geo enrichment rows={len(rows)} "
        f"population={pop_count} area_km2={area_count} "
        f"latitude={lat_count} longitude={lon_count}"
    )


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


def _resolve_election_date(year, election_type, election_date_by_year=None):
    mapping = election_date_by_year
    if mapping is None:
        if election_type == "presidentielle":
            mapping = ELECTION_DATE_BY_YEAR
        elif election_type == "municipale":
            mapping = MUNICIPAL_ELECTION_DATE_BY_YEAR
        else:
            mapping = {}

    if int(year) not in mapping:
        raise RuntimeError(
            f"Missing election date for election_type={election_type}, year={int(year)}"
        )
    return mapping[int(year)]


def _get_or_create_election(
    cur,
    year,
    scope="departement",
    election_type="presidentielle",
    election_date_by_year=None,
):
    election_date = _resolve_election_date(
        year=year,
        election_type=election_type,
        election_date_by_year=election_date_by_year,
    )
    round_no = 1

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
    normalized_name = str(candidate_name or "").strip().upper()
    if not normalized_name:
        raise RuntimeError("Empty candidate_name is not allowed.")

    ref_party_code, ref_party_name = _party_reference_for_candidate(normalized_name)

    cur.execute(
        """
        SELECT candidate_id, party_name, party_code
        FROM candidate
        WHERE candidate_name = %s
        ORDER BY candidate_id ASC
        LIMIT 1
        """,
        (normalized_name,),
    )
    row = cur.fetchone()
    if row:
        candidate_id, party_name, party_code = row
        needs_update = (
            party_name is None
            or str(party_name).strip() == ""
            or party_code is None
            or str(party_code).strip() == ""
        )
        if needs_update:
            cur.execute(
                """
                UPDATE candidate
                SET party_name = COALESCE(party_name, %s),
                    party_code = COALESCE(party_code, %s)
                WHERE candidate_id = %s
                """,
                (ref_party_name, ref_party_code, candidate_id),
            )
        return candidate_id

    cur.execute(
        """
        INSERT INTO candidate (candidate_name, party_name, party_code)
        VALUES (%s, %s, %s)
        RETURNING candidate_id
        """,
        (normalized_name, ref_party_name, ref_party_code),
    )
    return cur.fetchone()[0]


def _backfill_candidate_party_fields(cur):
    cur.execute(
        """
        SELECT candidate_id, candidate_name, party_name, party_code
        FROM candidate
        """
    )
    rows = cur.fetchall()
    if not rows:
        return

    updates = []
    for candidate_id, candidate_name, party_name, party_code in rows:
        ref_party_code, ref_party_name = _party_reference_for_candidate(candidate_name)
        next_party_name = party_name if party_name is not None and str(party_name).strip() else ref_party_name
        next_party_code = party_code if party_code is not None and str(party_code).strip() else ref_party_code

        if next_party_name != party_name or next_party_code != party_code:
            updates.append((next_party_name, next_party_code, candidate_id))

    if not updates:
        return

    cur.executemany(
        """
        UPDATE candidate
        SET party_name = %s,
            party_code = %s
        WHERE candidate_id = %s
        """,
        updates,
    )
    print(f"[load] candidate party backfill rows={len(updates)}")


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


def _upsert_geo_communes_from_results(cur, commune_results_df):
    if commune_results_df.empty:
        return

    required = {"insee_code", "commune_name", "dept_code"}
    if not required.issubset(set(commune_results_df.columns)):
        return

    communes = (
        commune_results_df[list(required)]
        .dropna(subset=["insee_code", "dept_code"])
        .copy()
    )
    if communes.empty:
        return

    communes["insee_code"] = communes["insee_code"].astype(str).str.strip()
    communes["dept_code"] = communes["dept_code"].astype(str).str.zfill(2)
    communes["commune_name"] = communes["commune_name"].fillna("").astype(str).str.strip()
    communes["commune_name"] = communes["commune_name"].where(
        communes["commune_name"] != "",
        communes["insee_code"],
    )
    communes = communes[communes["insee_code"].str.len() == 5]
    communes = communes[communes["dept_code"].isin(TARGET_DEPT_CODES)]
    communes = communes.drop_duplicates(subset=["insee_code"], keep="last")
    if communes.empty:
        return

    payload = [
        (row.insee_code, row.commune_name, row.dept_code)
        for row in communes.itertuples(index=False)
    ]
    cur.executemany(
        """
        INSERT INTO geo_commune (insee_code, commune_name, dept_code)
        VALUES (%s, %s, %s)
        ON CONFLICT (insee_code) DO UPDATE
        SET commune_name = EXCLUDED.commune_name,
            dept_code = EXCLUDED.dept_code
        """,
        payload,
    )
    print(f"[load] geo communes upsert rows={len(payload)}")


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


def _ensure_feature_tables(cur):
    ddl_statements = [
        """
        CREATE TABLE IF NOT EXISTS commune_year_economy (
          insee_code char(5) NOT NULL REFERENCES geo_commune (insee_code),
          year integer NOT NULL,
          median_standard_of_living numeric,
          declared_income_median numeric,
          taxable_households_share numeric,
          social_benefits_income_share numeric,
          establishments_count numeric,
          business_creations_count numeric,
          business_creation_rate numeric,
          unemployment_rate numeric,
          poverty_rate numeric,
          PRIMARY KEY (insee_code, year)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS commune_year_education (
          insee_code char(5) NOT NULL REFERENCES geo_commune (insee_code),
          year integer NOT NULL,
          no_diploma_rate_20_24 numeric,
          school_leavers_20_24_count numeric,
          school_leavers_20_24_no_diploma_count numeric,
          PRIMARY KEY (insee_code, year)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS commune_year_demography (
          insee_code char(5) NOT NULL REFERENCES geo_commune (insee_code),
          year integer NOT NULL,
          population_total numeric,
          population_age_75_plus_count numeric,
          population_age_75_plus_share numeric,
          life_expectancy_women numeric,
          life_expectancy_men numeric,
          PRIMARY KEY (insee_code, year)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS commune_year_environment (
          insee_code char(5) NOT NULL REFERENCES geo_commune (insee_code),
          year integer NOT NULL,
          social_housing_share numeric,
          catnat_communes_flood_count numeric,
          catnat_communes_storm_count numeric,
          catnat_communes_drought_count numeric,
          PRIMARY KEY (insee_code, year)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS commune_year_election_context (
          election_type text NOT NULL,
          round smallint NOT NULL,
          year integer NOT NULL,
          insee_code char(5) NOT NULL REFERENCES geo_commune (insee_code),
          registered integer,
          votes_cast integer,
          votes_valid integer,
          turnout_rate numeric,
          valid_ballot_rate numeric,
          invalid_ballot_rate numeric,
          winner_share numeric,
          candidate_count integer,
          PRIMARY KEY (election_type, round, year, insee_code)
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_commune_year_economy_year ON commune_year_economy (year)",
        "CREATE INDEX IF NOT EXISTS idx_commune_year_education_year ON commune_year_education (year)",
        "CREATE INDEX IF NOT EXISTS idx_commune_year_demography_year ON commune_year_demography (year)",
        "CREATE INDEX IF NOT EXISTS idx_commune_year_environment_year ON commune_year_environment (year)",
        "CREATE INDEX IF NOT EXISTS idx_commune_year_election_context_year ON commune_year_election_context (year)",
    ]
    for sql in ddl_statements:
        cur.execute(sql)


def _refresh_commune_feature_tables_from_indicators(cur):
    # Economy
    cur.execute(
        """
        INSERT INTO commune_year_economy (
            insee_code,
            year,
            median_standard_of_living,
            declared_income_median,
            taxable_households_share,
            social_benefits_income_share,
            establishments_count,
            business_creations_count,
            business_creation_rate,
            unemployment_rate,
            poverty_rate
        )
        SELECT
            iv.insee_code,
            iv.year,
            MAX(CASE WHEN i.indicator_code = 'median_standard_of_living' THEN iv.value END),
            MAX(CASE WHEN i.indicator_code = 'declared_income_median' THEN iv.value END),
            MAX(CASE WHEN i.indicator_code = 'taxable_households_share' THEN iv.value END),
            MAX(CASE WHEN i.indicator_code = 'social_benefits_income_share' THEN iv.value END),
            MAX(CASE WHEN i.indicator_code = 'establishments_count' THEN iv.value END),
            MAX(CASE WHEN i.indicator_code = 'business_creations_count' THEN iv.value END),
            MAX(CASE WHEN i.indicator_code = 'business_creation_rate' THEN iv.value END),
            MAX(CASE WHEN i.indicator_code = 'unemployment_rate' THEN iv.value END),
            MAX(CASE WHEN i.indicator_code = 'poverty_rate' THEN iv.value END)
        FROM indicator_value iv
        JOIN indicator i ON i.indicator_id = iv.indicator_id
        WHERE i.indicator_code IN (
            'median_standard_of_living',
            'declared_income_median',
            'taxable_households_share',
            'social_benefits_income_share',
            'establishments_count',
            'business_creations_count',
            'business_creation_rate',
            'unemployment_rate',
            'poverty_rate'
        )
        GROUP BY iv.insee_code, iv.year
        ON CONFLICT (insee_code, year) DO UPDATE
        SET
            median_standard_of_living = EXCLUDED.median_standard_of_living,
            declared_income_median = EXCLUDED.declared_income_median,
            taxable_households_share = EXCLUDED.taxable_households_share,
            social_benefits_income_share = EXCLUDED.social_benefits_income_share,
            establishments_count = EXCLUDED.establishments_count,
            business_creations_count = EXCLUDED.business_creations_count,
            business_creation_rate = EXCLUDED.business_creation_rate,
            unemployment_rate = EXCLUDED.unemployment_rate,
            poverty_rate = EXCLUDED.poverty_rate
        """
    )

    # Education
    cur.execute(
        """
        INSERT INTO commune_year_education (
            insee_code,
            year,
            no_diploma_rate_20_24,
            school_leavers_20_24_count,
            school_leavers_20_24_no_diploma_count
        )
        SELECT
            iv.insee_code,
            iv.year,
            MAX(CASE WHEN i.indicator_code = 'no_diploma_rate_20_24' THEN iv.value END),
            MAX(CASE WHEN i.indicator_code = 'school_leavers_20_24_count' THEN iv.value END),
            MAX(CASE WHEN i.indicator_code = 'school_leavers_20_24_no_diploma_count' THEN iv.value END)
        FROM indicator_value iv
        JOIN indicator i ON i.indicator_id = iv.indicator_id
        WHERE i.indicator_code IN (
            'no_diploma_rate_20_24',
            'school_leavers_20_24_count',
            'school_leavers_20_24_no_diploma_count'
        )
        GROUP BY iv.insee_code, iv.year
        ON CONFLICT (insee_code, year) DO UPDATE
        SET
            no_diploma_rate_20_24 = EXCLUDED.no_diploma_rate_20_24,
            school_leavers_20_24_count = EXCLUDED.school_leavers_20_24_count,
            school_leavers_20_24_no_diploma_count = EXCLUDED.school_leavers_20_24_no_diploma_count
        """
    )

    # Demography
    cur.execute(
        """
        INSERT INTO commune_year_demography (
            insee_code,
            year,
            population_total,
            population_age_75_plus_count,
            population_age_75_plus_share,
            life_expectancy_women,
            life_expectancy_men
        )
        SELECT
            iv.insee_code,
            iv.year,
            MAX(CASE WHEN i.indicator_code = 'population_total' THEN iv.value END),
            MAX(CASE WHEN i.indicator_code = 'population_age_75_plus_count' THEN iv.value END),
            MAX(CASE WHEN i.indicator_code = 'population_age_75_plus_share' THEN iv.value END),
            MAX(CASE WHEN i.indicator_code = 'life_expectancy_women' THEN iv.value END),
            MAX(CASE WHEN i.indicator_code = 'life_expectancy_men' THEN iv.value END)
        FROM indicator_value iv
        JOIN indicator i ON i.indicator_id = iv.indicator_id
        WHERE i.indicator_code IN (
            'population_total',
            'population_age_75_plus_count',
            'population_age_75_plus_share',
            'life_expectancy_women',
            'life_expectancy_men'
        )
        GROUP BY iv.insee_code, iv.year
        ON CONFLICT (insee_code, year) DO UPDATE
        SET
            population_total = EXCLUDED.population_total,
            population_age_75_plus_count = EXCLUDED.population_age_75_plus_count,
            population_age_75_plus_share = EXCLUDED.population_age_75_plus_share,
            life_expectancy_women = EXCLUDED.life_expectancy_women,
            life_expectancy_men = EXCLUDED.life_expectancy_men
        """
    )

    # Environment
    cur.execute(
        """
        INSERT INTO commune_year_environment (
            insee_code,
            year,
            social_housing_share,
            catnat_communes_flood_count,
            catnat_communes_storm_count,
            catnat_communes_drought_count
        )
        SELECT
            iv.insee_code,
            iv.year,
            MAX(CASE WHEN i.indicator_code = 'social_housing_share' THEN iv.value END),
            MAX(CASE WHEN i.indicator_code = 'catnat_communes_flood_count' THEN iv.value END),
            MAX(CASE WHEN i.indicator_code = 'catnat_communes_storm_count' THEN iv.value END),
            MAX(CASE WHEN i.indicator_code = 'catnat_communes_drought_count' THEN iv.value END)
        FROM indicator_value iv
        JOIN indicator i ON i.indicator_id = iv.indicator_id
        WHERE i.indicator_code IN (
            'social_housing_share',
            'catnat_communes_flood_count',
            'catnat_communes_storm_count',
            'catnat_communes_drought_count'
        )
        GROUP BY iv.insee_code, iv.year
        ON CONFLICT (insee_code, year) DO UPDATE
        SET
            social_housing_share = EXCLUDED.social_housing_share,
            catnat_communes_flood_count = EXCLUDED.catnat_communes_flood_count,
            catnat_communes_storm_count = EXCLUDED.catnat_communes_storm_count,
            catnat_communes_drought_count = EXCLUDED.catnat_communes_drought_count
        """
    )


def _refresh_commune_election_context_table(cur):
    cur.execute(
        """
        INSERT INTO commune_year_election_context (
            election_type,
            round,
            year,
            insee_code,
            registered,
            votes_cast,
            votes_valid,
            turnout_rate,
            valid_ballot_rate,
            invalid_ballot_rate,
            winner_share,
            candidate_count
        )
        SELECT
            e.election_type,
            e.round,
            EXTRACT(YEAR FROM e.election_date)::int AS year,
            er.insee_code,
            MAX(er.registered) AS registered,
            MAX(er.votes_cast) AS votes_cast,
            MAX(er.votes_valid) AS votes_valid,
            CASE
                WHEN MAX(er.registered) > 0
                THEN MAX(er.votes_cast)::numeric / MAX(er.registered)::numeric
                ELSE NULL
            END AS turnout_rate,
            CASE
                WHEN MAX(er.votes_cast) > 0
                THEN MAX(er.votes_valid)::numeric / MAX(er.votes_cast)::numeric
                ELSE NULL
            END AS valid_ballot_rate,
            CASE
                WHEN MAX(er.votes_cast) > 0
                THEN 1.0 - (MAX(er.votes_valid)::numeric / MAX(er.votes_cast)::numeric)
                ELSE NULL
            END AS invalid_ballot_rate,
            MAX(er.vote_share) AS winner_share,
            COUNT(DISTINCT er.candidate_id) AS candidate_count
        FROM election_result er
        JOIN election e ON e.election_id = er.election_id
        WHERE e.scope = 'commune'
        GROUP BY
            e.election_type,
            e.round,
            EXTRACT(YEAR FROM e.election_date)::int,
            er.insee_code
        ON CONFLICT (election_type, round, year, insee_code) DO UPDATE
        SET
            registered = EXCLUDED.registered,
            votes_cast = EXCLUDED.votes_cast,
            votes_valid = EXCLUDED.votes_valid,
            turnout_rate = EXCLUDED.turnout_rate,
            valid_ballot_rate = EXCLUDED.valid_ballot_rate,
            invalid_ballot_rate = EXCLUDED.invalid_ballot_rate,
            winner_share = EXCLUDED.winner_share,
            candidate_count = EXCLUDED.candidate_count
        """
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


def _load_election_results(
    results_df,
    scope="departement",
    election_type="presidentielle",
    election_date_by_year=None,
):
    if results_df.empty:
        print("No election rows extracted from data.gouv.")
        return

    if scope not in {"departement", "commune"}:
        raise ValueError(f"Unsupported scope: {scope}")

    conn = get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                _ensure_votes_nullable(cur)
                _ensure_idf_geo(cur)
                _ensure_indicator_catalog(cur)
                _ensure_feature_tables(cur)
                _backfill_candidate_party_fields(cur)

                target_insee_codes_for_geo = None
                if scope == "commune":
                    _upsert_geo_communes_from_results(cur, results_df)
                    if "insee_code" in results_df.columns:
                        insee_series = results_df["insee_code"].astype(str).str.strip()
                        insee_series = insee_series[insee_series.str.len() == 5]
                        target_insee_codes_for_geo = sorted(insee_series.unique().tolist())

                _load_geo_enrichment(cur, target_insee_codes=target_insee_codes_for_geo)

                candidate_cache = {}
                for year in sorted(results_df["year"].unique()):
                    election_id = _get_or_create_election(
                        cur,
                        int(year),
                        scope=scope,
                        election_type=election_type,
                        election_date_by_year=election_date_by_year,
                    )
                    year_df = results_df[results_df["year"] == year].copy()
                    if year_df.empty:
                        continue

                    if scope == "departement":
                        year_df["insee_code"] = year_df["dept_code"].astype(str).str.zfill(2) + "000"
                    else:
                        year_df["insee_code"] = year_df["insee_code"].astype(str).str.strip()
                        year_df = year_df[year_df["insee_code"].str.len() == 5]
                        year_df = year_df[year_df["dept_code"].astype(str).str.zfill(2).isin(TARGET_DEPT_CODES)]
                        year_df = year_df.dropna(subset=["insee_code"])

                    target_insee = sorted(year_df["insee_code"].unique().tolist())
                    if not target_insee:
                        continue

                    cur.execute(
                        """
                        DELETE FROM election_result
                        WHERE election_id = %s AND insee_code = ANY(%s)
                        """,
                        (election_id, target_insee),
                    )

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
                                record.insee_code,
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
                        f"[load] type={election_type} scope={scope} year={int(year)} rows={len(rows)} "
                        f"{'departments' if scope == 'departement' else 'communes'}="
                        f"{year_df['insee_code'].nunique() if scope == 'commune' else year_df['dept_code'].nunique()}"
                    )

                if scope == "departement" and election_type == "presidentielle":
                    _load_turnout_indicator_values(cur, results_df)
                if scope == "commune":
                    _refresh_commune_election_context_table(cur)
    finally:
        conn.close()


def run_election_pipeline():
    results_df = _collect_all_results()
    if results_df.empty:
        raise RuntimeError("No election data extracted. Check source URLs in run_etl.py.")

    _load_election_results(results_df, scope="departement")
    print(
        "[done] loaded election results for years "
        f"{', '.join(str(y) for y in sorted(results_df['year'].unique()))} "
        f"on target departments {', '.join(sorted(TARGET_DEPT_CODES))}."
    )


def run_election_commune_pipeline():
    results_df = _collect_all_commune_results()
    if results_df.empty:
        raise RuntimeError("No commune-level election data extracted. Check commune source URLs.")

    _load_election_results(results_df, scope="commune")
    print(
        "[done] loaded commune-level election results for years "
        f"{', '.join(str(y) for y in sorted(results_df['year'].unique()))} "
        f"(communes={results_df['insee_code'].nunique()})."
    )


def run_municipal_commune_pipeline():
    results_df = _collect_municipal_commune_results()
    if results_df.empty:
        raise RuntimeError(
            "No municipal commune-level data extracted. "
            "Set MUNICIPAL_RESULTS_CSV_PATH to a valid CSV and enable LOAD_MUNICIPAL_RESULTS=true."
        )

    supported_years = set(MUNICIPAL_ELECTION_DATE_BY_YEAR.keys())
    available_years = sorted(set(int(y) for y in results_df["year"].dropna().unique().tolist()))
    dropped_years = [year for year in available_years if year not in supported_years]
    if dropped_years:
        print(
            "[warn] municipal years ignored (missing election date mapping): "
            + ", ".join(str(y) for y in dropped_years)
        )
    results_df = results_df[results_df["year"].isin(sorted(supported_years))].copy()
    if results_df.empty:
        raise RuntimeError(
            "Municipal CSV loaded but no supported years remain. "
            "Supported years: "
            + ", ".join(str(y) for y in sorted(MUNICIPAL_ELECTION_DATE_BY_YEAR.keys()))
        )

    _load_election_results(
        results_df,
        scope="commune",
        election_type="municipale",
        election_date_by_year=MUNICIPAL_ELECTION_DATE_BY_YEAR,
    )
    print(
        "[done] loaded municipal commune-level election results for years "
        f"{', '.join(str(y) for y in sorted(results_df['year'].unique()))} "
        f"(communes={results_df['insee_code'].nunique()})."
    )


def collect_election_results_dataframe():
    return _collect_all_results()


def collect_election_results_commune_dataframe():
    return _collect_all_commune_results()


def collect_municipal_commune_results_dataframe():
    return _collect_municipal_commune_results()


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
                _load_geo_enrichment(cur)
                _ensure_indicator_catalog(cur)
                _ensure_feature_tables(cur)
                _load_socio_indicator_values(cur, values_df)
                _refresh_commune_feature_tables_from_indicators(cur)
                _refresh_commune_election_context_table(cur)
    finally:
        conn.close()

    print(
        "[done] loaded socio-economic indicator values for years "
        f"{values_df['year'].min()}-{values_df['year'].max()} "
        f"(rows={len(values_df)})."
    )


def main():
    run_election_pipeline()
    if LOAD_COMMUNE_RESULTS:
        run_election_commune_pipeline()
    if LOAD_MUNICIPAL_RESULTS:
        run_municipal_commune_pipeline()
    run_socio_economic_pipeline()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
