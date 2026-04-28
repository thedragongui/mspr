# Architecture BI - 3 couches

Date de reference: 20 avril 2026.

## Vue d'ensemble
Architecture decisionnelle organisee en 3 couches conformement a la grille MSPR.

```mermaid
flowchart LR
    A[Couche 1<br/>Collecte/Ingestion] --> B[Couche 2<br/>Stockage/Modelisation]
    B --> C[Couche 3<br/>Restitution/Usage]
```

## Couche 1 - Collecte/Ingestion
- Sources: data.gouv, INSEE ODD, geo.api.gouv.fr
- Outils: Python ETL (`src/etl/run_etl.py`), Airflow (DAG `mspr_idf_presidentielles_etl`)
- Format manipules: CSV, TXT, XLSX, API JSON
- Sortie intermediaire: cache `data/raw/data_gouv_cache`

## Couche 2 - Stockage/Modelisation
- SGBD: PostgreSQL (Docker)
- Modele: relationnel normalise + datamarts thematiques
- Tables coeur: `election`, `candidate`, `election_result`, `indicator`, `indicator_value`
- Datamarts: `commune_year_economy`, `commune_year_education`, `commune_year_demography`, `commune_year_environment`, `commune_year_election_context`
- Documentation modele: [mcd.md](/C:/Users/guilhem/Documents/mspr/docs/mcd.md)

## Couche 3 - Restitution
- Data science: scripts ML (`src/ml/train.py`, `src/ml/train_commune_tuned.py`, `src/ml/train_reliable_all_years.py`)
- Dataviz statique: Matplotlib (`src/dashboard/build_dashboard.py`)
- Dataviz interactive: HTML interactif (`src/dashboard/build_dashboard_interactive.py`)
- Supports: `data/processed/dashboard/`, `slides/`, `docs/`

## Choix ELT / entrepot
- Approche retenue: ELT sur PostgreSQL
- Justification:
  - Traçabilite simple des transformations
  - Reproductibilite en environnement Docker
  - Facile a auditer pour un POC MSPR

## Limites POC
- Pas de cluster distribue (Spark/Flink) car volumetrie moderee
- Pas de cube OLAP deploye dans un outil BI dedie
