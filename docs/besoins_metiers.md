# Besoins Metiers (Annexe Cahier des Charges)

Date de formalisation: 20 avril 2026.

## Contexte metier
Electio Analytics souhaite disposer d'un dispositif decisionnel pour:
- suivre l'evolution electorale en Ile-de-France,
- expliquer les resultats par des facteurs socio-economiques,
- simuler des tendances sur la prochaine election presidentielle.

## Parties prenantes
1. Direction generale  
Attente: vision macro fiable et rapidement communicable.

2. Pole etudes/data  
Attente: donnees historisees, tracables et exploitables pour la modelisation.

3. Pole communication/strategie  
Attente: visualisations compréhensibles pour des non-techniciens.

## Questions metiers prioritaires
1. Quels blocs politiques progressent/reculent selon les territoires et les annees ?
2. Quels indicateurs socio-economiques sont les plus associes aux variations electorales ?
3. Les predictions produites sont-elles suffisamment fiables pour une lecture strategique ?
4. Peut-on comparer reel vs predit de maniere claire par annee, territoire et bloc ?

## Exigences fonctionnelles
1. Integrer au minimum les presidentielles 1969-2022 (tour 1), IDF.
2. Centraliser les resultats election + indicateurs socio-economiques dans une base unique.
3. Permettre l'analyse au niveau departement et commune.
4. Produire des dashboards lisibles et un rapport interactif.
5. Entraîner et evaluer des modeles ML en split temporel.

## Exigences non fonctionnelles
1. Reproductibilite du pipeline (scripts + orchestration).
2. Traceabilite des sources et des transformations.
3. Temps d'execution compatible soutenance/demo.
4. Documentation lisible pour jury non technique.

## KPI retenus pour la soutenance
1. Couverture temporelle des elections chargees.
2. Taux de completude des colonnes critiques (`registered`, `votes_cast`, `votes_valid`, `votes`, `vote_share`).
3. Qualite ML: R2, MAE, RMSE.
4. Disponibilite des livrables: schema BDD, MCD, dashboards, fichiers de metrics.

## Critere d'acceptation MSPR (operationnel)
- Le processus data complet (collecte -> restitution) est executable et documente.
- Au moins un modele ML depasse R2 > 0.5 sur la cible evaluee.
- Les resultats sont restituables en format statique + interactif.
