# Indicateurs et questions

## Indicateur le plus correle aux resultats
Dans l'etat actuel du projet (10 presidentielles en Ile-de-France), l'indicateur le plus exploitable reste le taux de participation:

- `taux_participation = votants / inscrits`
- `taux_abstention = 1 - taux_participation`

Ce n'est pas encore un "meilleur" indicateur metier au sens socio-economique: les correlations lineaires observees avec la part de vote par candidat restent faibles (ordre de grandeur < 0.2 en valeur absolue sur le tour 1, Ile-de-France). Conclusion: il faut integrer des indicateurs INSEE (revenu, chomage, structure d'age, CSP) pour obtenir une relation predictive plus robuste.

## Definition de l'apprentissage supervise
L'apprentissage supervise consiste a entrainer un modele avec:

- des variables d'entree `X` (indicateurs socio-eco, participation, historique electoral)
- une variable cible `y` connue pendant l'entrainement

Dans ce projet, la cible principale est continue (`vote_share`), donc le probleme est d'abord une regression:

- exemples de modeles: regression lineaire, random forest regressor, gradient boosting regressor
- metriques de suivi: MAE, RMSE, R2

Workflow minimal:

1. Construire un jeu d'apprentissage (departement, annee, indicateurs, cible).
2. Separer entrainement/test (split temporel si possible).
3. Entrainer plusieurs modeles.
4. Evaluer et retenir le modele le plus stable et interpretable.

## Definition de l'accuracy
`accuracy` est une metrique de classification:

- `accuracy = (nombre de predictions correctes) / (nombre total de predictions)`

Important pour ce projet:

- Si on predit directement `vote_share` (regression), `accuracy` n'est pas la metrique principale.
- `accuracy` devient pertinente si on transforme la cible en classes (ex: "candidat gagnant", "bloc politique majoritaire", "classe de score faible/moyen/fort").
- En regression, privilegier MAE/RMSE/R2.

## Autres indicateurs pertinents
Priorite aux indicateurs disponibles au niveau departement (ou proxy avec justification):

- Demographie: population, densite, part 18-24, part 65+, evolution population.
- Socio-economie: taux de chomage, mediane de revenu, taux de pauvrete, niveau de diplome.
- Structure socio-professionnelle: repartition CSP, part ouvriers/employes/cadres.
- Tissu economique: nombre d'entreprises, creations d'entreprises, secteurs dominants.
- Contexte electoral: participation historique, abstention, resultats tours precedents.
- Territoire: urbanite/ruralite, distance aux poles urbains, acces services publics.

Indicateurs effectivement branches dans l'ETL:

- `unemployment_rate` (INSEE `taux_chom_bit`, total)
- `poverty_rate` (INSEE `taux_pvt`, total)
- `median_standard_of_living` (INSEE `niveau_vie_median`)
- `no_diploma_rate_20_24` (INSEE `part_20_24_sortis_nondip`)
- `social_housing_share` (INSEE `part_pls`)

Criteres de selection:

- disponibilite publique et tracable
- granularite compatible avec `insee_code`
- couverture temporelle coherente avec la date electorale
- qualite (completude, coherence, faible taux de valeurs manquantes)
