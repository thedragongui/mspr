# MSPR Big Data - Electio Analytics POC

Perimetre: region Ile-de-France (departements 75, 77, 78, 91, 92, 93, 94, 95).
Election cible: 10 dernieres presidentielles (1969 a 2022), premier tour.
Objectif: predire la part de vote d'un candidat/parti a partir d'indicateurs socio-economiques et d'historiques electoraux.
Stack: Python + PostgreSQL (Docker) + Airflow + Matplotlib.

## Demarrage rapide

1. Copier `.env.example` vers `.env` et ajuster les variables.
2. Lancer tous les services (Postgres + pgAdmin + Airflow): `docker compose up -d --build`
   - Visualisation BDD: `http://localhost:8081`
   - Interface Airflow: `http://localhost:8080` (admin/password)
   - Login pgAdmin: email `admin@mspr.com`, mot de passe `admin` (modifiable via `.env`).
   - Dans pgAdmin, creer un server PostgreSQL:
     - Hostname/address: `db`
     - Port: `5432`
     - Maintenance DB: `mspr_electio`
     - Username/Password: selon `.env` (par defaut `mspr` / `mspr_password`)
3. Creer l'env Python et installer les deps:
   - `python -m venv .venv` (selon la version de python)
   - `python3 -m venv .venv`
   - Activer le venv:
     - **Linux / macOS:** `source .venv/bin/activate`
     - **Windows (PowerShell):** `.venv\Scripts\Activate.ps1`
     - **Windows (CMD):** `.venv\Scripts\activate.bat`
4) Le schema est charge au premier demarrage via `sql/schema.sql`.
   Si vous changez le schema: `docker compose down -v` puis `docker compose up -d`.
   5) Lancer le pipeline: `python src/etl/run_etl.py`
5) Lancer le pipeline (depuis la racine du projet, avec le venv active):
   - `python -m src.etl.run_etl`
   - Les resultats electoraux sont recuperes automatiquement depuis les ressources data.gouv configurees dans `src/etl/run_etl.py`.
   - Les indicateurs socio-eco sont alimentes depuis la source INSEE `ODD_DEP` (dataset "Indicateurs territoriaux de developpement durable").
   - Les fichiers telecharges sont caches dans `data/raw/data_gouv_cache/`.
   - Les indicateurs actuellement charges: `unemployment_rate`, `poverty_rate`, `median_standard_of_living`, `no_diploma_rate_20_24`, `social_housing_share`.
6) Generer le dashboard Matplotlib:
   - `python src/dashboard/build_dashboard.py`
   - `python -m src.dashboard.build_dashboard` (depuis la racine du projet)
   - Sortie: `data/processed/dashboard/idf_dashboard_matplotlib.png`
7) Ouvrir les notebooks si besoin.
8) **Machine Learning** (modele predictif supervise) :
   - Depuis la racine du projet : `python -m src.ml.train --target extreme_droite --model ridge` (cible part extreme droite, R² stabilise)
   - Options : `--no-db` (chargement ETL sans base), `--model rf`, `--test-years 2017,2022`, `--no-stable-r2` (toutes features)
   - Sorties : `data/processed/ml/model.joblib` et `data/processed/ml/metrics.json`
   - **Interpretation du R²** (soutenance/jury) : `docs/interpretation_r2.md`
- **Données pour améliorer le R²** : `docs/amelioration_r2_donnees.md`
   - Notebook : `notebooks/02_model.ipynb`

## Orchestration Airflow
1) Demarrer Airflow (et ses dependances) depuis le compose unique:
   - `docker compose up -d --build airflow`
2) Ouvrir:
   - `http://localhost:8080` (admin/admin)
3) DAG:
   - `mspr_idf_presidentielles_etl` (`load_presidential_results` -> `load_socio_economic_indicators` -> `build_matplotlib_dashboard`)

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
- `src/` scripts ETL et ML
- `src/dashboard/` generation dashboard Matplotlib
- `src/ml/` modele predictif (regression part de vote, features socio-eco + lags)
- `airflow/` DAGs et configuration Airflow
- `data/raw/` sources brutes
- `data/clean/` donnees nettoyees
- `data/processed/` jeux de travail
- `notebooks/` EDA + modele
- `powerbi/` dossier historique (non prioritaire)
- `slides/` support soutenance
