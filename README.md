# MSPR Big Data - Electio Analytics POC

Perimetre: region Ile-de-France (departements 75, 77, 78, 91, 92, 93, 94, 95).
Election cible: 10 dernieres presidentielles (1969 a 2022), premier tour.
Objectif: predire la part de vote d'un candidat/parti a partir d'indicateurs socio-economiques et d'historiques electoraux.
Stack: Python + PostgreSQL (Docker) + Airflow + PowerBI.

## Demarrage rapide
1) Copier `.env.example` vers `.env` et ajuster les variables.
2) Lancer Postgres: `docker compose up -d`
3) Creer l'env Python et installer les deps:
   - `python -m venv .venv`
   - `.venv\Scripts\Activate.ps1`
   - `pip install -r requirements.txt`
4) Le schema est charge au premier demarrage via `sql/schema.sql`.
   Si vous changez le schema: `docker compose down -v` puis `docker compose up -d`.
5) Lancer le pipeline: `python src/etl/run_etl.py`
   - Les resultats electoraux sont recuperes automatiquement depuis les ressources data.gouv configurees dans `src/etl/run_etl.py`.
   - Les indicateurs socio-eco sont alimentes depuis la source INSEE `ODD_DEP` (dataset "Indicateurs territoriaux de developpement durable").
   - Les fichiers telecharges sont caches dans `data/raw/data_gouv_cache/`.
   - Les indicateurs actuellement charges: `unemployment_rate`, `poverty_rate`, `median_standard_of_living`, `no_diploma_rate_20_24`, `social_housing_share`.
6) Ouvrir les notebooks ou PowerBI.

## Orchestration Airflow
1) Demarrer la base:
   - `docker compose up -d db`
2) Demarrer Airflow:
   - `docker compose -f docker-compose.yml -f docker-compose.airflow.yml up -d --build airflow`
3) Ouvrir:
   - `http://localhost:8080` (admin/admin)
4) DAG:
   - `mspr_idf_presidentielles_etl` (`load_presidential_results` puis `load_socio_economic_indicators`)

## Livrables
- Dossier de synthese: `docs/` (cadrage, sources, mcd, methodo)
- Jeu de donnees nettoye: `data/clean/` (CSV ou export SQL)
- Code: `src/` et `sql/`
- Support de soutenance: `slides/`

## Clefs de jointure attendues
- `insee_code` + `year` pour les indicateurs (`insee_code` departemental de type `75000`, `77000`, etc.)
- `insee_code` + `election_date` + `round` pour les resultats electoraux

## Arborescence
- `docs/` documentation projet
- `sql/` schema Postgres
- `src/` scripts ETL
- `airflow/` DAGs et configuration Airflow
- `data/raw/` sources brutes
- `data/clean/` donnees nettoyees
- `data/processed/` jeux de travail
- `notebooks/` EDA + modele
- `powerbi/` consignes PowerBI
- `slides/` support soutenance
