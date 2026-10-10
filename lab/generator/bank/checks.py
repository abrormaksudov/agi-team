"""Invariants the generated bank must satisfy before anything is written."""

import polars as pl

from .write import Sink


def _ledger(frame: pl.DataFrame, name: str, passive: bool = False) -> None:
    """Active accounts grow by debits, passive (customer money) by credits."""
    f = frame.sort("account_id", "_v")
    sign = -1 if passive else 1
    movement = sign * (pl.col("debit_turnover") - pl.col("credit_turnover"))
    roll = f.filter(pl.col("closing_balance") != pl.col("opening_balance") + movement)
    assert roll.is_empty(), f"{name}: closing balance does not roll forward ({roll.height} rows)"
    chain = f.with_columns(pl.col("closing_balance").shift(1).over("account_id").alias("prev")).filter(
        pl.col("prev").is_not_null() & (pl.col("prev") != pl.col("opening_balance")))
    assert chain.is_empty(), f"{name}: opening != previous closing ({chain.height} rows)"


def check(sink: Sink, snapshot: int, end: int) -> None:
    turnover = sink.frame("tranzaxis", "tx", "account_turnover")
    _ledger(turnover, "tranzaxis.account_turnover")
    negative = turnover.join(sink.frame("tranzaxis", "tx", "contract_account").select("account_id", "account_role"),
                             on="account_id").filter(pl.col("closing_balance") < 0)
    assert negative.is_empty(), f"tranzaxis: negative balances on {negative['account_role'].unique().to_list()}"

    balances = sink.frame("iabs", "core", "account_balance")
    _ledger(balances, "iabs.account_balance", passive=True)
    assert balances.filter(pl.col("closing_balance") < 0).is_empty(), "iabs: negative account balance"

    sched = sink.frame("tranzaxis", "tx", "payment_schedule").unique("schedule_line_id", keep="first")
    contracts = sink.frame("tranzaxis", "tx", "contract").filter(pl.col("contract_type") == "microloan").unique("contract_id")
    sums = sched.filter(pl.col("debt_kind") == "principal").group_by("contract_id").agg(pl.col("scheduled_amount").sum())
    bad = sums.join(contracts.select("contract_id", "principal_amount"), on="contract_id").filter(
        pl.col("scheduled_amount") != pl.col("principal_amount"))
    assert bad.is_empty(), f"microloan schedules do not sum to principal ({bad.height})"

    customers = set(sink.frame("iabs", "core", "customer")["customer_id"].to_list())
    linked = set(sink.frame("mobile", "users", "app_user")["core_customer_id"].drop_nulls().to_list())
    assert linked <= customers, "app_user.core_customer_id without a customer"
    clients = set(sink.frame("tranzaxis", "tx", "client")["client_id"].to_list())
    assert set(sink.frame("tranzaxis", "tx", "contract")["client_id"].to_list()) <= clients, "contract without client"

    for (source, schema, table), parts in sink.parts.items():
        frame = pl.concat(parts, how="diagonal_relaxed")
        late = frame.filter(pl.col("_v") > end)
        assert late.height == 0 or table in ("operating_day",), f"{source}.{schema}.{table}: rows after the end day"
