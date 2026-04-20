# Securite et conformite RGPD

Date de reference: 20 avril 2026.

## Perimetre juridique
- Donnees manipulees: donnees electorales agregees et indicateurs territoriaux publics.
- Source principale: open data (data.gouv / INSEE).
- Nature des donnees: pas de donnees personnelles directes exploitees dans le POC.

## Principes appliques
1. Minimisation
- Le POC conserve les champs necessaires a l'analyse et a la prediction.
- Pas de collecte de donnees nominatives citoyennes.

2. Licences et proprietes intellectuelles
- Les sources sont listees et tracables dans [sources.md](/C:/Users/guilhem/Documents/mspr/docs/sources.md).
- Les jeux de donnees sont utilises selon leur regime open data.

3. Confidentialite operationnelle
- Secrets techniques externalises dans `.env` (DB user/password).
- Acces base borne au reseau Docker du projet.
- Separation des services (`db`, `pgadmin`, `airflow`) via `docker-compose.yml`.

4. Integrite et qualite
- Regles qualite explicites avant entrainement dans [data_quality.py](/C:/Users/guilhem/Documents/mspr/src/ml/data_quality.py).
- Controles de coherence metier (bornes [0,1], contraintes votes/inscrits, doublons).

5. Traceabilite
- Pipelines scriptes et rejouables (`python -m src.etl.run_etl`).
- Orchestration Airflow et artefacts de sortie versionnables (`data/processed/*`).

## Mesures de durcissement recommandees (prochaine etape)
- Remplacer les identifiants par defaut (Airflow admin/admin, pgAdmin admin/admin).
- Ajouter une politique de rotation des secrets.
- Activer chiffrement TLS sur les acces externes aux interfaces d'admin.
- Ajouter un registre de traitements (format RGPD) meme si donnees publiques.

## Position par rapport a la grille MSPR
- Critere securite/juridique: partiellement couvert techniquement et documente.
- Action pour passer au niveau maximal: formaliser une procedure RSSI complete (controle d'acces, journalisation securite, plan de reponse incident).
