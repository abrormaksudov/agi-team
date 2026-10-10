"""Bank simulator, not part of the DWH: one run plays one operating day.

Loads lab/data/<source>/<oper_day>/<schema>.<table>.csv (written by lab/generator) into each source
system, upserting by the table's primary key: new rows are inserted, changed rows (a contract's status,
a schedule line's payment) replace their earlier version. Then closes the day by triggering dbt__cod
with that oper_day, like the core system's closing-of-day event in a real bank. Never scheduled: one
trigger per day, oper_day in the conf; the first day (the snapshot) carries all history.
"""

from pathlib import Path

from _greenplum import provide_cursor
from airflow.providers.standard.operators.trigger_dagrun import TriggerDagRunOperator
from airflow.sdk import Param, chain, dag, task
from psycopg import Cursor, sql
from useful_func import read_yaml

CONFIG = read_yaml("sim__operating_day.yml")
DATA_DIR = Path("/opt/lab/data")


PRIMARY_KEY = """
    select a.attname
    from pg_index i
    join pg_attribute a on a.attrelid = i.indrelid and a.attnum = any(i.indkey)
    where i.indrelid = %s::regclass and i.indisprimary
"""


@task
def load_day(source: str, conn_id: str, params: dict | None = None) -> None:
    oper_day = params.get("oper_day")

    @provide_cursor(conn_id)
    def load(cursor: Cursor = None) -> None:
        for path in sorted((DATA_DIR / source / oper_day).glob("*.csv")):
            schema, table = path.stem.split(".")
            target = sql.Identifier(schema, table)
            with open(path) as file:
                header = file.readline().strip().split(",")
                columns = sql.SQL(", ").join(map(sql.Identifier, header))
                cursor.execute(PRIMARY_KEY, [f"{schema}.{table}"])
                key = [row[0] for row in cursor.fetchall()]
                cursor.execute(sql.SQL("create temp table stage (like {})").format(target))
                file.seek(0)
                with cursor.copy(sql.SQL("copy stage ({}) from stdin with (format csv, header true)").format(columns)) as copy:
                    while chunk := file.read(1 << 20):
                        copy.write(chunk)
            match = sql.SQL(" and ").join(sql.SQL("t.{0} = s.{0}").format(sql.Identifier(k)) for k in key)
            cursor.execute(sql.SQL("delete from {} t using stage s where {}").format(target, match))
            cursor.execute(sql.SQL("insert into {} ({}) select {} from stage").format(target, columns, columns))
            print(f"{source}: {schema}.{table} — {cursor.rowcount} rows for {oper_day}")
            cursor.execute("drop table stage")

    load()


@dag(
    dag_id="sim__operating_day",
    schedule=None,
    max_active_runs=1,
    params={"oper_day": Param(type="string", format="date")},
    is_paused_upon_creation=False,
    tags=["simulator"],
)
def operating_day():
    loads = [
        load_day.override(task_id=f"load__{source}")(source, config.get("conn_id"))
        for source, config in CONFIG.items()
    ]
    close_day = TriggerDagRunOperator(
        task_id="close_day",
        trigger_dag_id="dbt__cod",
        trigger_run_id="oper_day__{{ params.oper_day }}",
        conf={"oper_day": "{{ params.oper_day }}"},
        reset_dag_run=True,
        wait_for_completion=True,
        poke_interval=5,
        failed_states=["failed"],
    )
    chain(loads, close_day)


operating_day()
