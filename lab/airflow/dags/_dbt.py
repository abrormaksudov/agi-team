import logging
from datetime import UTC, date, datetime, timedelta, timezone
from json import dumps
from os import getenv
from pathlib import Path

from _bash import execute_bash_cmd
from _greenplum import provide_cursor
from airflow.sdk import chain, task
from psycopg import Cursor
from useful_func import read_json

MANIFEST = read_json(f"{getenv('DBT_TARGET_PATH')}/manifest.json")
# The catalog's dbt ingestion reads its manifest here: compiled SQL of every model, which `dbt parse` and the
# per-model builds leave empty and OpenMetadata parses for column-level lineage. Test results stay in DBT_TARGET_PATH.
CATALOG_TARGET_PATH = Path(getenv("DBT_TARGET_PATH")).parent / "catalog"

UZT = timezone(timedelta(hours=5))

logger = logging.getLogger(__name__)


def _oper_day_vars(oper_day: str) -> dict:
    """The operating day as a whole UZT day, in the vars the models read."""
    start = datetime.combine(date.fromisoformat(oper_day), datetime.min.time(), UZT)
    return {
        "oper_day": oper_day,
        "load_from_datetime": start.astimezone(UTC).isoformat(),
        "load_to_datetime": (start + timedelta(days=1)).astimezone(UTC).isoformat(),
    }


def _dbt_vars(context: dict) -> dict:
    oper_day = context.get("params").get("oper_day")
    if not oper_day:
        raise ValueError("oper_day is required: trigger with conf {'oper_day': 'YYYY-MM-DD'}")
    return {"dwh_job_id": context.get("run_id")} | _oper_day_vars(oper_day)


@task
def base_build_model_task(node_name: str, **context) -> None:
    dbt_vars = _dbt_vars(context)

    cmd = f"dbt build --select {node_name} --vars '{dumps(dbt_vars)}'"
    test_results = []
    try:
        execute_bash_cmd(cmd, stdout_func=lambda log: _collect_test_result(log, test_results))
    finally:
        _flush_test_results(test_results)


@task(trigger_rule="all_done")
def compile_for_catalog(**context) -> None:
    """Compile every model into the catalog's manifest (CATALOG_TARGET_PATH), for column-level lineage."""
    cmd = f"DBT_WRITE_JSON=True dbt compile --target-path {CATALOG_TARGET_PATH} --vars '{dumps(_dbt_vars(context))}'"
    execute_bash_cmd(cmd)


@task(trigger_rule="all_done")
def test_all(**context) -> None:
    """Run every test once more into one run_results.json, the file the catalog reads test results from; the per-model
    builds already logged their results to dq_test_log, so this run does not log again."""
    cmd = f"DBT_WRITE_JSON=True dbt test --vars '{dumps(_dbt_vars(context))}'"
    execute_bash_cmd(cmd)


@task(trigger_rule="one_failed", retries=0)
def watcher() -> None:
    """Fails the run when any task failed: the catalog tasks run after failures too (all_done), so without this leaf a
    failed model would leave the run green."""
    raise RuntimeError("a task of this run failed, see the failed task's log")


def _collect_test_result(log: dict, results: list) -> None:
    if log.get("info", {}).get("name") != "LogTestResult":
        return

    data = log.get("data", {})
    node_info = data.get("node_info", {})

    test_name = data.get("name", "")
    attached_node = data.get("attached_node", "")
    if attached_node:
        model_name = attached_node.rsplit(".", 1)[-1]
        if test_name.startswith(f"{model_name}__"):
            test_name = test_name[len(model_name) + 2 :]
    else:
        model_name, _, test_name = test_name.rpartition("__")
        if not model_name:
            model_name = None

    results.append(
        (
            node_info.get("unique_id"),
            model_name,
            test_name,
            node_info.get("node_started_at"),
            data.get("status"),
            data.get("execution_time", 0),
            node_info.get("node_finished_at"),
        )
    )


@provide_cursor()
def _flush_test_results(results: list, cursor: Cursor = None) -> None:
    if not results:
        return
    cursor.executemany(
        """
            insert into dbt_test__audit.dq_test_log
            values (%s, %s, %s, %s, %s, %s, %s)
        """,
        results,
    )


def get_parent_node_task(node_id: str) -> list[str]:
    parent_node_ids = []
    for parent_node_id in MANIFEST.get("parent_map").get(node_id):
        parent_node = MANIFEST.get("nodes").get(parent_node_id)
        if parent_node:
            config = parent_node.get("config") or {}
            materialized = config.get("materialized")
            tags = config.get("tags") or []
            if materialized == "ephemeral" or "archived" in tags:
                parent_node_ids.extend(get_parent_node_task(parent_node_id))
            else:
                parent_node_ids.append(parent_node_id)

    return parent_node_ids


def generate_tasks_by_tag(tag: str) -> list:
    node_ids = [
        node_id
        for node_id, node_info in MANIFEST.get("nodes").items()
        if node_info.get("resource_type") == "model" and tag in node_info.get("tags")
    ]

    tasks = {}
    for node_id in node_ids:
        node_name = MANIFEST.get("nodes").get(node_id).get("name")
        tasks[node_id] = base_build_model_task.override(task_id=node_name)(node_name)

    for node_id in node_ids:
        for parent_node_id in get_parent_node_task(node_id):
            if not tasks.get(parent_node_id):
                # A production DWH would wait here with a cross-DAG sensor; the lab runs every model in one DAG.
                raise ValueError(f"{node_id} depends on {parent_node_id}, which is not tagged {tag!r}")
            chain(tasks[parent_node_id], tasks[node_id])

    return list(tasks.values())
