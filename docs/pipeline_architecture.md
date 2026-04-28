# Pipeline data et architecture BI

Date de reference: 28 avril 2026.

## Vue d'ensemble (3 couches)
1. Collecte / ingestion
- Sources: data.gouv, INSEE ODD, geo.api.gouv.fr
- Outils: Python ETL (`src/etl/run_etl.py`), orchestration Airflow

2. Stockage / modelisation
- SGBD: PostgreSQL
- Approche: ELT
- Objets: tables coeur + datamarts thematiques + schema BI

3. Restitution
- Dashboards statiques (Matplotlib)
- Dashboard interactif (HTML + Plotly / Streamlit)
- Modeles ML pour la prediction

## Flux ETL (logique)
1. Extraction multi-sources (CSV/TXT/XLSX/API)
2. Normalisation (types, colonnes, INSEE, nomenclatures)
3. Controle qualite (nulls, bornes, coherence votes, doublons)
4. Chargement en base
5. Construction features ML
6. Entrainement/evaluation
7. Restitution

## Strategie big data
## Ingestion
- Acquisition heterogene avec cache local (`data/raw/data_gouv_cache`) pour tracabilite/rejeu.

## Stockage
- Choix ELT PostgreSQL:
  - lisibilite et auditabilite MSPR,
  - cout/complexite maitrises pour un POC,
  - integration directe avec ML et dashboards.

## Traitement distribue (position)
- Non active en POC (mono-instance volontaire).
- Bascule envisagee si volumetrie/SLA depassent les seuils cibles.

## Restitution de valeur
- Indicateurs decisionnels par territoire et annee.
- Comparaison reel vs predit.
- Livrables exploitables par metiers et jury.

## Orchestration
- Manuel: `python -m src.etl.run_etl`
- Planifie: DAG `mspr_idf_presidentielles_etl`

## Tracabilite
- Sources: [sources.md](/C:/Users/guilhem/Documents/mspr/docs/sources.md)
- Schema: [schema.sql](/C:/Users/guilhem/Documents/mspr/sql/schema.sql)
- Export nettoye: `python -m src.etl.export_clean_datasets`
