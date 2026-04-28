# Modelisation ML et precision

Date de reference: 28 avril 2026.

## Approche
- Apprentissage supervise pour predire la part de vote.
- Split temporel strict (train sur passe, test sur elections futures).
- Metriques: `R2`, `MAE`, `RMSE`.

## Resultats de reference (test 2022, commune)
Source: `data/processed/ml/reliable_probe_all_2022_summary.csv`

| Cible | R2 |
|---|---|
| extreme_gauche | 0.8547 |
| gauche | 0.2188 |
| centre | 0.6204 |
| droite | 0.4418 |
| extreme_droite | 0.8051 |

## Interpretation jury
1. Un `R2` faible ou negatif reste possible en prediction electorale temporelle:
- faible taille d'echantillon historique,
- rupture de regimes politiques selon les annees,
- choix volontaire d'un split temporel realiste.

2. L'evaluation ne repose pas uniquement sur `R2`:
- `MAE` interpretable directement en points de vote,
- `RMSE` pour penaliser les ecarts importants.

## Reponses attendues dans le sujet
1. Indicateurs les plus correles: relies aux historiques de vote et a certains indicateurs socio-economiques.
2. Definition apprentissage supervise: apprentissage a partir de couples features/cible connus.
3. Degre de precision: combinaison `R2 + MAE + RMSE`.

## Plan d'amelioration
1. Ajouter des observations et enrichissements contextuels (securite, economie locale, densite, etc.).
2. Renforcer la maille commune sur les annees historiques partielles.
3. Continuer le tuning cible par cible (notamment `gauche` et `droite`).

## References detaillees
- [interpretation_r2.md](/C:/Users/guilhem/Documents/mspr/docs/archive/legacy_2026-04-28/interpretation_r2.md)
- [amelioration_r2_donnees.md](/C:/Users/guilhem/Documents/mspr/docs/archive/legacy_2026-04-28/amelioration_r2_donnees.md)
- [indicateurs.md](/C:/Users/guilhem/Documents/mspr/docs/archive/legacy_2026-04-28/indicateurs.md)
