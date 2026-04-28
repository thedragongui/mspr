# Cadrage et besoins metiers

Date de reference: 28 avril 2026.

## Contexte
Electio Analytics veut valider, via un POC, une capacite de prevision electorale a moyen terme.
Le projet cible un perimetre geographique unique (Ile-de-France) avec une analyse a maille commune.

## Perimetre
- Region: Ile-de-France (`75`, `77`, `78`, `91`, `92`, `93`, `94`, `95`)
- Maille d'analyse principale: commune
- Scrutin: election presidentielle, premier tour
- Historique exploite: 1969-2022 (avec couverture commune complete surtout 2012-2022)

## Parties prenantes
1. Direction generale
- Attente: vision macro fiable et decisionnelle.

2. Pole etudes/data
- Attente: donnees historisees, tracables, exploitables en BI/ML.

3. Pole communication/strategie
- Attente: visualisations comprehensibles pour un public non technique.

## Questions metiers
1. Quels blocs politiques progressent ou reculent selon les territoires et les annees ?
2. Quels indicateurs socio-economiques sont les plus associes aux variations electorales ?
3. Le modele est-il assez fiable pour orienter des decisions strategiques ?
4. Comment comparer clairement reel et predit par annee et territoire ?

## Exigences fonctionnelles
1. Integrer resultats election + indicateurs socio-economiques dans une base unique.
2. Mettre en place un pipeline ETL reproductible.
3. Produire des restitutions statiques et interactives.
4. Entrainer et evaluer des modeles ML en split temporel.
5. Fournir un jeu de donnees nettoye en livrable.

## Exigences non fonctionnelles
1. Tracabilite des sources et transformations.
2. Rejouabilite de bout en bout (ETL + ML + dashboards).
3. Temps d'execution compatible demo/soutenance.
4. Documentation lisible par jury technique et non technique.

## KPI de soutenance
1. Couverture temporelle des elections chargees.
2. Completude des colonnes critiques (`registered`, `votes_cast`, `votes_valid`, `votes`, `vote_share`).
3. Qualite ML (`R2`, `MAE`, `RMSE`).
4. Disponibilite des livrables (`docs/`, `sql/`, `src/`, `data/clean/`, `slides/`).

## Critere d'acceptation MSPR (operationnel)
- Le processus data complet (collecte -> restitution) est executable et documente.
- Au moins un modele ML depasse `R2 > 0.5` sur la cible evaluee.
- Les resultats sont restituables en format statique et interactif.
