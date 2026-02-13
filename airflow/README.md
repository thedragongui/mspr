# Airflow

## Lancer Airflow
1) Demarrer la base projet:
   - `docker compose up -d db`
2) Demarrer Airflow:
   - `docker compose -f docker-compose.yml -f docker-compose.airflow.yml up -d --build airflow`
3) Ouvrir l'UI:
   - `http://localhost:8080`
   - user: `admin`
   - password: `admin`

## DAG disponible
- `mspr_idf_presidentielles_etl`
  - `load_presidential_results`
  - `load_socio_economic_indicators`
  - `build_matplotlib_dashboard`

## Arreter Airflow
- `docker compose -f docker-compose.yml -f docker-compose.airflow.yml stop airflow`
