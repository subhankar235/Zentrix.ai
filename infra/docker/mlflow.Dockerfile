FROM ghcr.io/mlflow/mlflow:v2.20.0

RUN pip install --no-cache-dir psycopg2-binary
