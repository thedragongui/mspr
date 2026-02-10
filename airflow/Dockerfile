FROM apache/airflow:2.10.5-python3.11

USER root
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
USER airflow
