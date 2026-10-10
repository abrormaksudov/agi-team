from datetime import UTC, datetime

import _scheduling as scheduling
from airflow.sdk import Param, dag
from useful_func import read_yaml

CONFIG = read_yaml("_dbt__common_dag.yml")


def create_dag(tag: str, config: dict) -> None:
    schedule = config.get("schedule")

    @dag(
        dag_id=f"dbt__{tag}",
        schedule=schedule,
        start_date=datetime.strptime(config.get("start_date", "2026-01-01"), "%Y-%m-%d").replace(tzinfo=UTC),
        dagrun_timeout=scheduling.dagrun_timeout(schedule),
        default_args={"owner": "dwh"} | scheduling.task_defaults(schedule),
        params={"oper_day": Param(None, type=["null", "string"], format="date")},
        is_paused_upon_creation=False,
        tags=["dbt", tag],
    )
    def generated_dag():
        from _dbt import compile_for_catalog, generate_tasks_by_tag, test_all, watcher
        from airflow.sdk import chain

        models = generate_tasks_by_tag(tag)
        catalog = [compile_for_catalog(), test_all()]
        chain(models, *catalog)
        chain([*models, *catalog], watcher())

    generated_dag()


for _tag, _config in CONFIG.items():
    create_dag(_tag, _config)
