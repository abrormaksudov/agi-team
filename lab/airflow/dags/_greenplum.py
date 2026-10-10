from collections.abc import Callable
from functools import wraps
from typing import Any

from airflow.sdk import Connection
from psycopg import connect


def provide_cursor(conn_id: str = "greenplum", autocommit: bool = False) -> Callable:
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            conn = Connection.get(conn_id)
            with connect(
                host=conn.host,
                port=conn.port,
                dbname=conn.schema,
                user=conn.login,
                password=conn.password,
                autocommit=autocommit,
            ) as connection, connection.cursor() as cursor:
                return func(*args, cursor=cursor, **kwargs)

        return wrapper

    return decorator
