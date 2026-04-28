# Cadrage

## Contexte
Electio Analytics veut valider une capacite de prevision electorale a moyen terme via un POC.
Le client attend un perimetre geographique unique et un pipeline traceable.

## Perimetre
- Region: Ile-de-France
- Niveau geo de travail: departement (75, 77, 78, 91, 92, 93, 94, 95)
- POC limite a une region unique pour la tracabilite et la volumetrie

## Cible
- Elections: 10 dernieres presidentielles (1969 a 2022)
- Tour cible: 1er tour (tous candidats)
- Variable cible: part de vote d'un candidat/parti
- Granularite: departement, election

## Hypotheses
- Les resultats election sont recuperables via data.gouv
- Les indicateurs socio-eco prioritaires seront agreges au niveau departemental
- Alignement temporel: indicateurs de l'annee N -> election de l'annee N
- Les codes INSEE departementaux (format `XX000`) servent de cle de jointure

## Contraintes
- Donnees publiques uniquement
- Reproductibilite via ETL automatise
