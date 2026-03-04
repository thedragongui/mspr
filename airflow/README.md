# Airflow

## Lancer Airflow
1) Demarrer Airflow (et ses dependances) depuis le compose unique:
   - `docker compose up -d --build airflow`
2) Ouvrir l'UI:
   - `http://localhost:8080`
   - user: `admin`
   - password: `admin`

## DAG disponible
- `mspr_idf_presidentielles_etl`
  - `load_presidential_results`
  - `load_socio_economic_indicators`
  - `build_matplotlib_dashboard`

## Arreter Airflow
- `docker compose stop airflow`
