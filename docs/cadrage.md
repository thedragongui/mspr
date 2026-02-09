# Cadrage

## Contexte
Electio Analytics veut valider une capacite de prevision electorale a moyen terme via un POC.
Le client attend un perimetre geographique unique et un pipeline traceable.

## Perimetre
- Departement: Herault (code 34)
- Niveau geo: commune (INSEE)
- POC limite a un territoire unique pour la tracabilite et la volumetrie

## Cible
- Election: presidentielle 2002 (2 tours)
- Tour cible: tour 1 (tous candidats)
- Variable cible: part de vote d'un candidat/parti
- Granularite: commune, election, tour

## Hypotheses
- Les indicateurs sont disponibles a la commune et a l'annee
- Alignement temporel: indicateurs de l'annee N -> election de l'annee N
- Les codes INSEE sont la cle principale de jointure
- Les resultats presidentiels 2002 sont disponibles par commune

## Contraintes
- Donnees publiques uniquement
- Reproductibilite via ETL automatise
