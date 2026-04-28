# Strategie Big Data (Collecte -> Traitement -> Restitution)

Date de reference: 20 avril 2026.

## Objectif
Aligner explicitement la strategie technique avec la grille MSPR:
- ingestion adaptee aux sources heterogenes,
- stockage argumente,
- pipeline de traitement modelise,
- criteres de passage au distribue.

## 1) Ingestion
Technologies retenues:
1. Python (pandas, requests) pour l'acquisition multi-format (CSV/TXT/XLSX/API).
2. Airflow pour l'orchestration et la rejouabilite.
3. Cache local des sources pour la traçabilite (`data/raw/data_gouv_cache`).

Justification:
- Format des sources tres heterogene.
- Besoin de normalisation forte avant chargement.
- Besoin de rejouer les imports en soutenance.

## 2) Stockage
Choix retenu: ELT sur PostgreSQL.

Pourquoi:
1. Volumetrie actuelle POC maitrisee.
2. Modele relationnel transparent et auditable.
3. Compatibilite directe avec les scripts ML et dashboards.

Resultat:
- stockage normalise (tables coeur)
- datamarts thematiques (`commune_year_*`)
- datamart BI multidimensionnel (`sql/bi_datamart.sql`)

## 3) Pipeline de traitement
Pipeline logique:
1. Extraction des resultats election et indicateurs socio-economiques.
2. Normalisation (types, colonnes, INSEE).
3. Controles qualite (doublons, valeurs hors bornes, coherence des comptes).
4. Chargement des tables relationnelles.
5. Construction des features ML.
6. Entrainement + evaluation temporelle.
7. Restitution (Matplotlib + HTML interactif).

## 4) Traitement distribue: position et seuil de bascule
Etat actuel:
- pipeline non distribue (mono-instance) volontaire.

Justification:
- volumetrie POC insuffisante pour justifier Spark/Flink.
- priorite a la lisibilite et la reproductibilite MSPR.

Seuils de bascule recommandes:
1. > 10M lignes brutes par cycle ETL regulier.
2. SLA < 15 min avec reentrainement frequent.
3. Multiples regions + enrichissements multi-sources lourds.

Roadmap distribuee (si seuils atteints):
1. Ingestion objet store (S3/MinIO) + zone bronze/silver/gold.
2. Traitement Spark (batch) ou Flink (streaming).
3. Lakehouse (Delta/Iceberg) + couches semantiques BI.

## 5) Restitution de valeur
1. Dashboards pilotables par filtres (annee, metrique, indicateur, cible ML).
2. Comparaison reel vs predit pour arbitrage metier.
3. Dossier de conformite documente pour soutenance/jury.
