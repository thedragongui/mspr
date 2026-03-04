"""
Mapping des candidats vers des familles politiques (élections présidentielles 1969-2022).
Permet d'agréger les parts de vote par tendance pour la modélisation.
"""
from __future__ import annotations

# Famille politique simplifiée pour les présidentielles en IDF
# Basé sur les candidats principaux par élection (étiquettes courantes)
CANDIDATE_TO_FAMILY: dict[str, str] = {
    # Extrême gauche / gauche radicale
    "ARTHAUD": "extreme_gauche",
    "ROUSSEL": "extreme_gauche",
    "MÉLENCHON": "extreme_gauche",
    "MELENCHON": "extreme_gauche",
    "BUFFET": "extreme_gauche",
    "LAGUILLER": "extreme_gauche",
    "HUE": "extreme_gauche",
    "BESANCENOT": "extreme_gauche",
    "JOLY": "extreme_gauche",  # EELV parfois classé à gauche
    # Gauche
    "HOLLANDE": "gauche",
    "ROYAL": "gauche",
    "JOSPIN": "gauche",
    "MITTERRAND": "gauche",
    "FABIUS": "gauche",
    "CRESSON": "gauche",
    "LALONDE": "gauche",
    "MACRON": "centre",  # 2017/2022
    "BAYROU": "centre",
    "LECANUET": "centre",
    "POUTOU": "extreme_gauche",
    "DUPONT-AIGNAN": "droite_nat",
    "LE PEN": "extreme_droite",
    "MARINE LE PEN": "extreme_droite",
    "PÉN": "extreme_droite",
    "CHIRAC": "droite",
    "SARKOZY": "droite",
    "BALLADUR": "droite",
    "GISCARD D ESTAING": "droite",
    "GISCARD": "droite",
    "VILLEPIN": "droite",
    "FILLON": "droite",
    "POMPIDOU": "droite",
    "PÉCRESSE": "droite",
    "PECRESSE": "droite",
    "ZEMMOUR": "extreme_droite",
    # Divers
    "LASSALLE": "divers",
    "ARTAUD": "extreme_gauche",
    "THOUY": "extreme_gauche",
    "HIDALGO": "gauche",
    "JADOT": "gauche",
    "TAUBIRA": "gauche",
    "POUTOU": "extreme_gauche",
}

# Valeur par défaut pour candidats non mappés (à traiter comme "autre")
DEFAULT_FAMILY = "autre"


def get_family(candidate_name: str) -> str:
    """Retourne la famille politique d'un candidat (nom canonique en majuscules)."""
    if not candidate_name:
        return DEFAULT_FAMILY
    name = str(candidate_name).strip().upper()
    return CANDIDATE_TO_FAMILY.get(name, DEFAULT_FAMILY)
