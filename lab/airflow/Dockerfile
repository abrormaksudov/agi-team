ARG AIRFLOW_VERSION=3.3.2
ARG UV_VERSION=0.12.23

FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv

FROM apache/airflow:${AIRFLOW_VERSION}-python3.12

USER root

COPY --from=uv /uv /uvx /usr/local/bin/

ENV DBT_PROFILES_DIR=/opt/dbt \
    DBT_PROJECT_DIR=/opt/dbt/dwh \
    DBT_TARGET_PATH=/opt/airflow/dbt-state/target \
    DBT_LOG_PATH=/opt/airflow/dbt-state/logs \
    DBT_PACKAGES_INSTALL_PATH=/opt/airflow/dbt-state/dbt_packages \
    UV_PROJECT_ENVIRONMENT=/opt/dbt-venv

COPY pyproject.toml uv.lock /tmp/project/

RUN set -eux \
    && cd /tmp/project \
    && UV_NO_CACHE=1 /usr/local/bin/uv sync --frozen --only-group dbt --no-install-project \
        --python python3.12 -q \
    && ln -s /opt/dbt-venv/bin/dbt /usr/local/bin/dbt \
    && rm -rf /tmp/project \
    && mkdir --parents /opt/airflow/dbt-state \
    && chown --recursive airflow:root /opt/airflow/dbt-state

ENV DBT_DEBUG=True \
    DBT_LOG_FORMAT=json \
    DBT_LOG_LEVEL_FILE=none \
    DBT_POPULATE_CACHE=False \
    DBT_SEND_ANONYMOUS_USAGE_STATS=False \
    DBT_USE_COLORS=False \
    DBT_USE_COLORS_FILE=False \
    DBT_WRITE_JSON=False

USER airflow

RUN dbt --version && airflow version
