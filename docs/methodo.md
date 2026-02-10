# Methodo

## ETL
1) Extraction: telechargement automatique depuis les ressources data.gouv configurees dans `src/etl/run_etl.py`
2) Normalisation: harmoniser noms de colonnes, types, codes INSEE
3) Qualite: controles (doublons, valeurs manquantes, bornes)
4) Chargement: insertion dans Postgres (tables de reference + faits)
5) Orchestration: DAG Airflow `mspr_idf_presidentielles_etl` pour automatiser les chargements

## EDA
- Stats descriptives par departement et par election
- Cartes et histogrammes
- Correlations indicateurs vs part de vote

## Modelisation
- Apprentissage supervise pour predire la part de vote
- Perimetre actuel: 1er tour des 10 dernieres presidentielles en Ile-de-France
- Split temporel (ex: entrainement sur elections N-1, test sur election N)
- Modeles candidats: regression lineaire, random forest, gradient boosting
- Metriques: MAE/RMSE (regression) + accuracy si discretisation

## Restitution
- Scenarios a 1/2/3 ans
- Visualisations claires pour non-techniciens
