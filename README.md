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
   - Pour 1969-2012, l'ETL privilegie les fichiers CSV `*_t1_circ.csv` (dataset data.gouv `elections-presidentielles-1965-2012`) pour recuperer `Inscrits`/`Votants`/`Exprimes`/`voix` et eliminer les `NULL` historiques sur `election_result`.
   - Fallback possible vers les XLSX historiques via `USE_CIRC_CSV_FOR_ELECTION_COUNTS=false`.
   - Migration niveau commune (scope `commune`) :
     - couverture complete 2012/2017/2022 via fichiers bureaux de vote (`txt`)
     - historique ajoute 1981/1988/1995/2002 via fichiers `cdsp_presi*t1_commp9000.csv` (communes > 9000 habitants)
     - activation via `LOAD_COMMUNE_RESULTS=true`.
   - Chargement municipal (optionnel, source CSV locale nettoyee) :
     - activer via `LOAD_MUNICIPAL_RESULTS=true`
     - chemin configurable via `MUNICIPAL_RESULTS_CSV_PATH` (defaut: `data/raw/external/municipales_commune.csv`)
     - colonnes minimales attendues: `year`, `insee_code`, `candidate_name` + (`votes` ou `vote_share`)
     - le scope charge est `commune`, `election_type='municipale'`, `round=1`.
   - Pour charger uniquement le niveau commune manuellement: `python -c "from src.etl.run_etl import run_election_commune_pipeline; run_election_commune_pipeline()"`.
   - Les indicateurs socio-eco sont alimentes depuis la source INSEE `ODD_DEP` (dataset "Indicateurs territoriaux de developpement durable").
   - Les fichiers telecharges sont caches dans `data/raw/data_gouv_cache/`.
   - Enrichissement geo auto (table `geo_commune`) :
     - departement (`XX000`) depuis ODD: `population` (`pop`) et `area_km2` (`surfcom`, converti en km2)
     - communes IDF depuis `geo.api.gouv.fr`: `population`, `surface` (convertie en km2), `latitude`, `longitude`
   - Desactivation via `ENRICH_GEO_FROM_ODD=false` et/ou `ENRICH_GEO_COORDS_FROM_GEO_API=false`.
   - Les indicateurs actuellement charges: `unemployment_rate`, `unemployment_rate_youth_15_24`, `unemployment_rate_women`, `unemployment_rate_men`, `poverty_rate`, `median_standard_of_living`, `no_diploma_rate_20_24`, `social_housing_share`, `life_expectancy_women`, `life_expectancy_men`, `long_term_jobseekers_share`, `jobseekers_de_count`, `jobseekers_abc_count`, `overindebtedness_cases_count`, `turnout_rate`, `population_total`, `establishments_count`, `business_creations_count`, `business_creation_rate`, `declared_income_median`, `taxable_households_share`, `social_benefits_income_share`, `school_leavers_20_24_count`, `school_leavers_20_24_no_diploma_count`, `population_age_75_plus_count`, `population_age_75_plus_share`, `catnat_communes_flood_count`, `catnat_communes_storm_count`, `catnat_communes_drought_count`.
   - Datamarts thematiques auto-crees/remplis en base: `commune_year_economy`, `commune_year_education`, `commune_year_demography`, `commune_year_environment`, `commune_year_election_context`.
6) Generer le dashboard Matplotlib:
   - `python src/dashboard/build_dashboard.py`
   - `python -m src.dashboard.build_dashboard` (depuis la racine du projet)
   - Sorties:
     - `data/processed/dashboard/idf_dashboard_matplotlib.png` (donnees election + socio)
     - `data/processed/dashboard/idf_predictions_matplotlib.png` (predictions ML vs reel, comparaison core/full, cible `extreme_droite`)
     - `data/processed/dashboard/idf_predictions_<target>_matplotlib.png` (autres cibles: `gauche`, `droite`, `centre`, `extreme_gauche`, etc.)
     - `data/processed/dashboard/idf_predictions_commune_tuned_matplotlib.png` (mode commune optimise par parti, avec resume R2/MAE)
7) Ouvrir les notebooks si besoin.
8) **Machine Learning** (modele predictif supervise) :
   - Depuis la racine du projet : `python -m src.ml.train --target extreme_droite --model ridge` (cible part extreme droite, RÃ‚Â² stabilise)
   - Option de granularite geo : `--scope departement` (defaut) ou `--scope commune` (2012/2017/2022).
   - Options : `--no-db` (chargement ETL sans base), `--model ridge|enet|rf|et|gbr|hgb`, `--test-years 2017,2022`, `--no-stable-r2`, `--no-core-only` (active toutes les features, y compris colonnes election agregees + indicateurs supplementaires disponibles en base), `--no-safe-predictions` (desactive le fallback securise vers le baseline lag)
   - Benchmark rapide commune (evite les runs qui stagnent): `python -m src.ml.benchmark_commune --test-years 2022 --max-seconds-per-target 150`
   - Variables d'env ML: `ML_USE_ALL_DB_INDICATORS=true|false` (defaut `true`) et `ML_EXTRA_SOCIO_INDICATORS=code1,code2`
   - Quand des municipales `commune` sont chargees, le dataset ML ajoute automatiquement:
     `municipal_turnout_rate_latest`, `municipal_valid_ballot_rate_latest`,
     `municipal_winner_share_latest`, `municipal_num_candidates_latest`,
     `municipal_hhi_latest`, `municipal_year_lag`.
   - Sorties : `data/processed/ml/model.joblib`, `data/processed/ml/metrics.json`, `data/processed/ml/predictions.csv`
   - Entrainement `commune` optimise par parti (objectif: R2 > 0 sur toutes les cibles du bloc principal):
     - `python -m src.ml.train_commune_tuned --test-years 2022 --min-train-year 2012`
     - sorties dans `data/processed/ml/commune_tuned/` (metrics + predictions par parti + resume global)
   - **Interpretation du RÃ‚Â²** (soutenance/jury) : `docs/interpretation_r2.md`
- **DonnÃƒÂ©es pour amÃƒÂ©liorer le RÃ‚Â²** : `docs/amelioration_r2_donnees.md`
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
