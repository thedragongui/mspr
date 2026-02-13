from datetime import datetime

from airflow import DAG
from airflow.operators.python import PythonOperator

from src.etl import run_etl
from src.dashboard import build_dashboard


with DAG(
    dag_id="mspr_idf_presidentielles_etl",
    description="Charge les resultats presidentiels IDF + indicateurs socio-eco INSEE",
    schedule="@monthly",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["mspr", "etl", "idf", "presidentielle"],
) as dag:
    load_presidential_results = PythonOperator(
        task_id="load_presidential_results",
        python_callable=run_etl.run_election_pipeline,
    )

    load_socio_economic_indicators = PythonOperator(
        task_id="load_socio_economic_indicators",
        python_callable=run_etl.run_socio_economic_pipeline,
    )

    build_matplotlib_dashboard = PythonOperator(
        task_id="build_matplotlib_dashboard",
        python_callable=build_dashboard.run_dashboard_pipeline,
    )

    load_presidential_results >> load_socio_economic_indicators >> build_matplotlib_dashboard
