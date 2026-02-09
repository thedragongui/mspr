# Methodo

## ETL
1) Extraction: telechargement manuel des jeux de donnees dans `data/raw/`
2) Normalisation: harmoniser noms de colonnes, types, codes INSEE
3) Qualite: controles (doublons, valeurs manquantes, bornes)
4) Chargement: insertion dans Postgres (tables de reference + faits)

## EDA
- Stats descriptives par commune et par election
- Cartes et histogrammes
- Correlations indicateurs vs part de vote

## Modelisation
- Apprentissage supervise pour predire la part de vote
- Pour 2002, tour 1 pour conserver tous les candidats; tour 2 optionnel pour comparaison
- Split temporel (ex: entrainement sur elections N-1, test sur election N)
- Modeles candidats: regression lineaire, random forest, gradient boosting
- Metriques: MAE/RMSE (regression) + accuracy si discretisation

## Restitution
- Scenarios a 1/2/3 ans
- Visualisations claires pour non-techniciens
