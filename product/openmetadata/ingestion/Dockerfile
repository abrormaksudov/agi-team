FROM docker.getcollate.io/openmetadata/ingestion:2.0.5

# Upstream ships six sample-data DAGs; without them the DAG volume starts empty.
RUN rm /opt/airflow/dags/airflow_*.py

# Drop with the first 2.0.x release that contains open-metadata/OpenMetadata#32031.
RUN --mount=type=bind,source=backport_32031.py,target=/tmp/backport_32031.py python /tmp/backport_32031.py
