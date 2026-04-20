# Flux ETL (BPM/ETL)

Date de reference: 20 avril 2026.

## Objectif
Formaliser le processus de collecte, structuration, controle qualite, chargement et restitution, en lien direct avec la grille MSPR.

## Diagramme de flux
```mermaid
flowchart TD
    A[Sources externes<br/>data.gouv + INSEE ODD + geo.api.gouv.fr] --> B[Extraction Python ETL<br/>src/etl/run_etl.py]
    B --> C[Zone brute<br/>data/raw/data_gouv_cache]
    C --> D[Normalisation<br/>colonnes, types, codes INSEE]
    D --> E[Regles qualite ETL<br/>doublons, nulls, bornes]
    E --> F[Chargement PostgreSQL<br/>tables de reference + faits]
    F --> G[Datamarts thematiques<br/>commune_year_*]
    G --> H[Jeux ML<br/>src/ml/data.py + features]
    H --> I[Entrainement/Evaluation ML<br/>src/ml/train*.py]
    G --> J[Dataviz<br/>Matplotlib + HTML interactif]
    I --> J
    J --> K[Livrables<br/>data/processed + slides]
```

## Orchestration
- Mode manuel: `python -m src.etl.run_etl`
- Mode planifie: DAG Airflow `mspr_idf_presidentielles_etl`

## Timing type (POC)
1. Extraction et cache des sources
2. Nettoyage/normalisation
3. Chargement BDD
4. Construction des features ML
5. Generation dashboards

## Traceabilite
- Sources: [sources.md](/C:/Users/guilhem/Documents/mspr/docs/sources.md)
- Schema BDD: [schema.sql](/C:/Users/guilhem/Documents/mspr/sql/schema.sql)
- MCD: [mcd.md](/C:/Users/guilhem/Documents/mspr/docs/mcd.md)
