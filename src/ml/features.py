"""
Candidate/party to political-family mapping for presidential elections.
Used to aggregate candidate vote shares into family vote shares.
"""
from __future__ import annotations

import re
import unicodedata

# Family used when no mapping is found.
DEFAULT_FAMILY = "autre"


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


# Candidate name mapping (normalized key -> family).
# Keep this list permissive because historical sources expose multiple
# variants (surname only, full name, with particles, etc.).
CANDIDATE_TO_FAMILY: dict[str, str] = {
    # Extreme left / radical left
    "ARTHAUD": "extreme_gauche",
    "ARTAUD": "extreme_gauche",
    "LAGUILLER": "extreme_gauche",
    "LAGUILLER ARLETTE": "extreme_gauche",
    "BESANCENOT": "extreme_gauche",
    "BESANCENOT OLIVIER": "extreme_gauche",
    "POUTOU": "extreme_gauche",
    "MELENCHON": "extreme_gauche",
    "ROUSSEL": "extreme_gauche",
    "HUE": "extreme_gauche",
    "HUE ROBERT": "extreme_gauche",
    "BUFFET": "extreme_gauche",
    "LAJOINIE": "extreme_gauche",
    "GLUCKSTEIN": "extreme_gauche",
    "GLUCKSTEIN DANIEL": "extreme_gauche",
    "BOUSSEL": "extreme_gauche",
    "KRIVINE": "extreme_gauche",
    "DUCLOS": "extreme_gauche",
    "MARCHAIS": "extreme_gauche",
    # Left
    "MITTERRAND": "gauche",
    "JOSPIN": "gauche",
    "JOSPIN LIONEL": "gauche",
    "HOLLANDE": "gauche",
    "ROYAL": "gauche",
    "HAMON": "gauche",
    "HIDALGO": "gauche",
    "JADOT": "gauche",
    "JOLY": "gauche",
    "TAUBIRA": "gauche",
    "TAUBIRA CHRISTIANE": "gauche",
    "MAMERE": "gauche",
    "MAMERE NOEL": "gauche",
    "VOYNET": "gauche",
    "CHEVENEMENT": "gauche",
    "CHEVENEMENT JEAN PIERRE": "gauche",
    "CREPEAU": "gauche",
    "BOUCHARDEAU": "gauche",
    "JUQUIN": "gauche",
    "LALONDE": "gauche",
    # Centre
    "MACRON": "centre",
    "BAYROU": "centre",
    "BAYROU FRANCOIS": "centre",
    "POHER": "centre",
    "LECANUET": "centre",
    "LEPAGE": "centre",
    "LEPAGE CORINNE": "centre",
    # Right
    "CHIRAC": "droite",
    "CHIRAC JACQUES": "droite",
    "SARKOZY": "droite",
    "FILLON": "droite",
    "BALLADUR": "droite",
    "POMPIDOU": "droite",
    "PECRESSE": "droite",
    "BARRE": "droite",
    "GISCARD D ESTAING": "droite",
    "DEBRE": "droite",
    "MADELIN": "droite",
    "BOUTIN": "droite",
    "BOUTIN CHRISTINE": "droite",
    "CHABAN DELMAS": "droite",
    "GARAUD": "droite",
    "ROYER": "droite",
    # Far right
    "LE PEN": "extreme_droite",
    "LE PEN JEAN MARIE": "extreme_droite",
    "MARINE LE PEN": "extreme_droite",
    "MEGRET": "extreme_droite",
    "MEGRET BRUNO": "extreme_droite",
    "ZEMMOUR": "extreme_droite",
    # National right / sovereignist
    "DUPONT AIGNAN": "droite_nat",
    "VILLIERS": "droite_nat",
    "SAINT JOSSE": "droite_nat",
    "SAINT JOSSE JEAN": "droite_nat",
    "ASSELINEAU": "droite_nat",
    # Misc
    "LASSALLE": "divers",
    "CHEMINADE": "divers",
    "BOVE": "divers",
    "DUCATEL": "divers",
    "HERAUD": "divers",
    "MULLER": "divers",
    "NIHOUS": "divers",
    "SCHIVARDI": "divers",
    "RENOUVIN": "divers",
    "SEBAG": "divers",
}

# Party-code mapping (as loaded in candidate.party_code by ETL).
PARTY_CODE_TO_FAMILY: dict[str, str] = {
    # Extreme left / radical left
    "LO": "extreme_gauche",
    "LFI": "extreme_gauche",
    "PCF": "extreme_gauche",
    "NPA": "extreme_gauche",
    "LCR": "extreme_gauche",
    "PT": "extreme_gauche",
    "MNR": "extreme_droite",
    # Left
    "PS": "gauche",
    "PRG": "gauche",
    "MRG": "gauche",
    "PSU": "gauche",
    "LV": "gauche",
    "EELV": "gauche",
    "FGDS": "gauche",
    "MDC": "gauche",
    "DVG": "gauche",
    # Centre
    "MODEM": "centre",
    "CD": "centre",
    "LREM_RE": "centre",
    # Right
    "LR": "droite",
    "UMP": "droite",
    "RPR": "droite",
    "RPR_UMP": "droite",
    "UDR": "droite",
    "UDF": "droite",
    "DL": "droite",
    "CNIP": "droite",
    "FRS": "droite",
    # Far right
    "FN_RN": "extreme_droite",
    "REC": "extreme_droite",
    # National right / sovereignist
    "DLF": "droite_nat",
    "CPNT": "droite_nat",
    "MPF": "droite_nat",
    "UPR": "droite_nat",
    # Misc
    "RES": "divers",
    "ECO": "divers",
    "ALT": "divers",
    "REG": "divers",
    "SP": "divers",
    "DEMO": "divers",
    "NAR": "divers",
}


def _candidate_lookup_keys(candidate_name: str | None) -> list[str]:
    normalized = _normalize_text(candidate_name)
    if not normalized:
        return []

    keys = [normalized]
    parts = normalized.split(" ")

    # Common two-token surnames.
    if normalized.startswith("LE PEN"):
        keys.append("LE PEN")
    if normalized.startswith("GISCARD D ESTAING"):
        keys.append("GISCARD D ESTAING")
    if normalized.startswith("CHABAN DELMAS"):
        keys.append("CHABAN DELMAS")
    if normalized.startswith("DUPONT AIGNAN"):
        keys.append("DUPONT AIGNAN")
    if normalized.startswith("SAINT JOSSE"):
        keys.append("SAINT JOSSE")

    # Fallbacks for "SURNAME FIRSTNAME" and occasional inverse forms.
    if len(parts) >= 2:
        keys.append(parts[0])
        keys.append(parts[-1])
        keys.append(" ".join(parts[:2]))

    # Deduplicate while preserving order.
    out = []
    seen = set()
    for key in keys:
        if key and key not in seen:
            out.append(key)
            seen.add(key)
    return out


def get_family(candidate_name: str) -> str:
    """Return family from candidate name variants."""
    for key in _candidate_lookup_keys(candidate_name):
        family = CANDIDATE_TO_FAMILY.get(key)
        if family:
            return family
    return DEFAULT_FAMILY


def get_family_from_party_code(party_code: str | None) -> str:
    """Return family from ETL party_code."""
    code = _normalize_text(party_code)
    if not code:
        return DEFAULT_FAMILY
    return PARTY_CODE_TO_FAMILY.get(code, DEFAULT_FAMILY)
