# Modelisation ML et precision

Date de reference: 7 mai 2026.

## Approche
- Apprentissage supervise pour predire la part de vote par bloc politique.
- Split temporel strict (train sur annees passees, test sur annee future).
- Metriques: `R2`, `MAE`, `RMSE`.

## Type de modele utilise (run de reference 2022)
Source: `data/processed/ml/reliable_probe_all_2022_summary.csv`

Le run de reference n'utilise pas un unique estimateur "global", mais un schema
hybride par cible:
1. Ancre departementale same-year: `dept_nowcast_anchor_residual`
2. Correction residuelle commune:
- `ridge` pour `centre`, `extreme_droite`, `extreme_gauche`
- `hgb` (HistGradientBoostingRegressor) pour `droite`, `gauche`
3. Blend final optionnel avec baseline lag (`blend_alpha` dans le resume)

## Resultats de reference (test 2022, commune)
Source: `data/processed/ml/reliable_probe_all_2022_summary.csv`

| Cible | R2 |
|---|---|
| extreme_gauche | 0.8547 |
| gauche | 0.2188 |
| centre | 0.6204 |
| droite | 0.4418 |
| extreme_droite | 0.8051 |

## Justification du choix
1. La prediction electorale en commune est sensible au bruit local: l'ancre
   departementale stabilise la prediction.
2. Le modele residuel capture l'heterogeneite intra-departement.
3. Le blend avec baseline lag limite les degradations en cas de faible signal.
4. Le split temporel reste conforme a un usage predictif reel (pas de melange
   aleatoire train/test).

## Verification "toutes les elections" pour predire 2022
Verification executee sur le code le 7 mai 2026.

Annees disponibles effectivement chargees:
1. Scope `departement`: `1969, 1974, 1981, 1988, 1995, 2002, 2007, 2012, 2017, 2022`
2. Scope `commune`: `1981, 1988, 1995, 2002, 2007, 2012, 2017, 2022`

Cas `train.py` (pipeline standard):
1. `--test-years latest` => test `2022`
2. Scope `commune` => train utilise toutes les annees disponibles avant 2022:
   `1981, 1988, 1995, 2002, 2007, 2012, 2017`

Cas `train_reliable_all_years.py` (run de reference du fichier ci-dessus):
1. Le train est borne par `--min-train-year`
2. Par defaut, le script est a `--min-train-year 2012`
3. Pour le fold `2022`, cela donne un train `2012, 2017` (donc pas toutes les
   elections historiques)

Conclusion:
- Si la question est "le pipeline peut-il utiliser toutes les elections pour 2022 ?"
  => Oui (ex. `train.py` scope commune, train 1981-2017).
- Si la question est "le run de reference `reliable_probe_all_2022` les utilise-t-il ?"
  => Non, il est coherent avec une fenetre recentre sur 2012-2017.

## Recommandation de tracabilite
Pour eviter l'ambiguite en soutenance, ajouter dans chaque summary ML:
1. `available_years`
2. `train_years_effective`
3. `test_years_effective`

## References detaillees
- [train.py](/C:/Users/guilhem/Documents/mspr/src/ml/train.py)
- [train_reliable_all_years.py](/C:/Users/guilhem/Documents/mspr/src/ml/train_reliable_all_years.py)
- [data.py](/C:/Users/guilhem/Documents/mspr/src/ml/data.py)
- [reliable_probe_all_2022_summary.csv](/C:/Users/guilhem/Documents/mspr/data/processed/ml/reliable_probe_all_2022_summary.csv)
- [reliable_probe_2022_summary.csv](/C:/Users/guilhem/Documents/mspr/data/processed/ml/reliable_probe_2022_summary.csv)
