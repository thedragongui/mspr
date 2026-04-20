"""
Entity normalization helpers for candidate/party-level forecasting.

Goals:
- keep a stable candidate identifier across naming variants;
- keep a stable party lineage identifier when party labels change over time.
"""
from __future__ import annotations

import re
import unicodedata


def _normalize_text(value: str | None) -> str:
    text = "" if value is None else str(value)
    text = text.strip().upper()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.replace("'", " ")
    text = text.replace("-", " ")
    text = re.sub(r"[^A-Z0-9 ]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


MULTI_TOKEN_SURNAMES = {
    "DUPONT AIGNAN",
    "SAINT JOSSE",
    "DE VILLIERS",
    "GISCARD D ESTAING",
    "CHABAN DELMAS",
}


# Party lineage ids normalize party renaming over time.
PARTY_CODE_TO_LINEAGE = {
    "PS": "PS_LINEAGE",
    "MRG": "PS_LINEAGE",
    "PRG": "PS_LINEAGE",
    "PSU": "PS_LINEAGE",
    "FGDS": "PS_LINEAGE",
    "MDC": "PS_LINEAGE",
    "DVG": "PS_LINEAGE",
    "LFI": "LFI_LINEAGE",
    "PCF": "PCF_LINEAGE",
    "LCR": "TROTSKY_LINEAGE",
    "LO": "TROTSKY_LINEAGE",
    "NPA": "TROTSKY_LINEAGE",
    "LREM_RE": "MACRONISTE_LINEAGE",
    "MODEM": "CENTRISTE_LINEAGE",
    "CD": "CENTRISTE_LINEAGE",
    "UDF": "CENTRE_DROITE_LINEAGE",
    "RPR": "DROITE_GOUV_LINEAGE",
    "UMP": "DROITE_GOUV_LINEAGE",
    "RPR_UMP": "DROITE_GOUV_LINEAGE",
    "LR": "DROITE_GOUV_LINEAGE",
    "UDR": "DROITE_GOUV_LINEAGE",
    "DL": "DROITE_GOUV_LINEAGE",
    "FRS": "DROITE_GOUV_LINEAGE",
    "CNIP": "DROITE_GOUV_LINEAGE",
    "FN_RN": "RN_LINEAGE",
    "MNR": "RN_LINEAGE",
    "REC": "RN_LINEAGE",
    "DLF": "SOUVERAINISTE_DROITE_LINEAGE",
    "UPR": "SOUVERAINISTE_DROITE_LINEAGE",
    "MPF": "SOUVERAINISTE_DROITE_LINEAGE",
    "CPNT": "SOUVERAINISTE_DROITE_LINEAGE",
    "LV": "ECOLOGISTE_LINEAGE",
    "EELV": "ECOLOGISTE_LINEAGE",
}

PARTY_ALIAS_TO_LINEAGE = {
    "RN": "RN_LINEAGE",
    "FRONT NATIONAL": "RN_LINEAGE",
    "RASSEMBLEMENT NATIONAL": "RN_LINEAGE",
    "FN": "RN_LINEAGE",
    "RECONQUETE": "RN_LINEAGE",
    "LR": "DROITE_GOUV_LINEAGE",
    "UMP": "DROITE_GOUV_LINEAGE",
    "RPR": "DROITE_GOUV_LINEAGE",
    "PS": "PS_LINEAGE",
    "PARTI SOCIALISTE": "PS_LINEAGE",
    "LFI": "LFI_LINEAGE",
    "LA FRANCE INSOUMISE": "LFI_LINEAGE",
    "LREM": "MACRONISTE_LINEAGE",
    "RENAISSANCE": "MACRONISTE_LINEAGE",
    "MACRONISTE": "MACRONISTE_LINEAGE",
    "MODEM": "CENTRISTE_LINEAGE",
    "EELV": "ECOLOGISTE_LINEAGE",
    "ECOLOGISTE": "ECOLOGISTE_LINEAGE",
}


# Fallback when party_code is missing (notably some older records with NR).
CANDIDATE_TO_LINEAGE = {
    "ARTHAUD": "TROTSKY_LINEAGE",
    "LAGUILLER": "TROTSKY_LINEAGE",
    "BESANCENOT": "TROTSKY_LINEAGE",
    "POUTOU": "TROTSKY_LINEAGE",
    "MELENCHON": "LFI_LINEAGE",
    "ROUSSEL": "PCF_LINEAGE",
    "HUE": "PCF_LINEAGE",
    "MARCHAIS": "PCF_LINEAGE",
    "MITTERRAND": "PS_LINEAGE",
    "JOSPIN": "PS_LINEAGE",
    "ROYAL": "PS_LINEAGE",
    "TAUBIRA": "PS_LINEAGE",
    "CHEVENEMENT": "PS_LINEAGE",
    "HAMON": "PS_LINEAGE",
    "HIDALGO": "PS_LINEAGE",
    "HOLLANDE": "PS_LINEAGE",
    "MACRON": "MACRONISTE_LINEAGE",
    "BAYROU": "CENTRISTE_LINEAGE",
    "CHIRAC": "DROITE_GOUV_LINEAGE",
    "SARKOZY": "DROITE_GOUV_LINEAGE",
    "FILLON": "DROITE_GOUV_LINEAGE",
    "PECRESSE": "DROITE_GOUV_LINEAGE",
    "BALLADUR": "DROITE_GOUV_LINEAGE",
    "POMPIDOU": "DROITE_GOUV_LINEAGE",
    "BOUTIN": "DROITE_GOUV_LINEAGE",
    "MADELIN": "DROITE_GOUV_LINEAGE",
    "BARRE": "CENTRE_DROITE_LINEAGE",
    "ZEMMOUR": "RN_LINEAGE",
    "MEGRET": "RN_LINEAGE",
    "JEAN_MARIE_LE_PEN": "RN_LINEAGE",
    "MARINE_LE_PEN": "RN_LINEAGE",
    "DUPONT_AIGNAN": "SOUVERAINISTE_DROITE_LINEAGE",
    "VILLIERS": "SOUVERAINISTE_DROITE_LINEAGE",
    "SAINT_JOSSE": "SOUVERAINISTE_DROITE_LINEAGE",
    "NIHOUS": "SOUVERAINISTE_DROITE_LINEAGE",
    "ASSELINEAU": "SOUVERAINISTE_DROITE_LINEAGE",
    "JADOT": "ECOLOGISTE_LINEAGE",
    "JOLY": "ECOLOGISTE_LINEAGE",
    "VOYNET": "ECOLOGISTE_LINEAGE",
    "MAMERE": "ECOLOGISTE_LINEAGE",
    "LEPAGE": "ECOLOGISTE_LINEAGE",
    "BOVE": "ECOLOGISTE_LINEAGE",
    "BUFFET": "PCF_LINEAGE",
    "GLUCKSTEIN": "TROTSKY_LINEAGE",
    "SCHIVARDI": "TROTSKY_LINEAGE",
}


def _slug(text: str) -> str:
    return text.replace(" ", "_")


def canonical_candidate_id(
    candidate_name: str | None,
    year: int | None = None,
    party_code: str | None = None,
) -> str:
    """
    Produce a stable candidate id from noisy historical naming.
    """
    normalized = _normalize_text(candidate_name)
    if not normalized:
        return "UNKNOWN_CANDIDATE"

    # Disambiguate LE PEN lineage by year (father vs daughter).
    if normalized.startswith("LE PEN") or normalized.endswith("LE PEN"):
        if year is not None and int(year) <= 2007:
            return "JEAN_MARIE_LE_PEN"
        if year is not None and int(year) >= 2012:
            return "MARINE_LE_PEN"
        return "LE_PEN"

    # Capture common two-token surnames.
    for multi in MULTI_TOKEN_SURNAMES:
        if normalized.startswith(multi):
            if multi == "DE VILLIERS":
                return "VILLIERS"
            return _slug(multi)

    tokens = normalized.split(" ")
    if not tokens:
        return "UNKNOWN_CANDIDATE"

    # Most ETL variants are "SURNAME FIRSTNAME" -> keep surname token.
    surname = tokens[0]
    candidate_id = _slug(surname)

    # Optional correction for NR-coded older datasets where one-token id is too generic.
    code = _normalize_text(party_code)
    if candidate_id == "LEPAGE" and code == "CAP21":
        return "CORINNE_LEPAGE"
    return candidate_id


def candidate_display_name(candidate_id: str) -> str:
    if not candidate_id:
        return "Unknown"
    if candidate_id == "JEAN_MARIE_LE_PEN":
        return "Jean-Marie Le Pen"
    if candidate_id == "MARINE_LE_PEN":
        return "Marine Le Pen"
    parts = str(candidate_id).replace("_", " ").split()
    return " ".join(p.capitalize() for p in parts)


def canonical_party_lineage(
    party_code: str | None,
    party_name: str | None = None,
    candidate_id: str | None = None,
) -> str:
    code = _normalize_text(party_code)
    if code in PARTY_CODE_TO_LINEAGE:
        return PARTY_CODE_TO_LINEAGE[code]

    name = _normalize_text(party_name)
    if name in PARTY_ALIAS_TO_LINEAGE:
        return PARTY_ALIAS_TO_LINEAGE[name]

    if candidate_id:
        candidate_key = str(candidate_id).strip().upper()
        if candidate_key in CANDIDATE_TO_LINEAGE:
            return CANDIDATE_TO_LINEAGE[candidate_key]

    if code:
        return f"PARTY_{_slug(code)}"
    if name:
        return f"PARTY_{_slug(name)}"
    return "PARTY_UNKNOWN"


def canonical_party_lineage_from_input(value: str | None) -> str:
    raw = _normalize_text(value)
    if not raw:
        raise RuntimeError("Entity parti vide.")
    if raw in PARTY_CODE_TO_LINEAGE:
        return PARTY_CODE_TO_LINEAGE[raw]
    if raw in PARTY_ALIAS_TO_LINEAGE:
        return PARTY_ALIAS_TO_LINEAGE[raw]
    if raw.endswith(" LINEAGE"):
        return _slug(raw)
    if raw.endswith("_LINEAGE"):
        return raw
    return f"PARTY_{_slug(raw)}"


def canonical_candidate_from_input(value: str | None) -> str:
    raw = _normalize_text(value)
    if not raw:
        raise RuntimeError("Entity candidat vide.")
    if raw.endswith("_LINEAGE"):
        raise RuntimeError("Le mode candidat attend un nom de candidat, pas un lineage de parti.")
    return canonical_candidate_id(raw, year=None, party_code=None)
