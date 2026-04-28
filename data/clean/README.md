# Jeux de donnees nettoyes (livrable MSPR)

Ce dossier contient les exports nettoyes, normalises et directement exploitables du POC.

## Fichiers
- `election_results_commune_t1_idf_clean.csv`
- `socio_indicators_idf_clean.csv`
- `manifest.json` (date de generation + volumetrie)

## Regles de nettoyage appliquees
1. Normalisation des identifiants geographiques (`insee_code` sur 5 caracteres, `dept_code` sur 2 caracteres).
2. Suppression des lignes incompletes sur les cles metier.
3. Suppression des ratios incoherents (`vote_share` et `turnout_rate` hors `[0,1]`).
4. Suppression des compteurs negatifs (`registered`, `votes_cast`, `votes_valid`, `votes`).
5. Dedoublonnage par cle metier (`year`, `insee_code`, `candidate_name` pour les resultats election ; `indicator_code`, `insee_code`, `year` pour les indicateurs).

## Regeneration
Depuis la racine du projet:

```powershell
python -m src.etl.export_clean_datasets
```
