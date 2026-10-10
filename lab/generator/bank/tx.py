"""tranzaxis tables: clients, contracts, contract accounts, turnover, schedules, cycles, delinquency, cards."""

from dataclasses import dataclass

import numpy as np
import polars as pl

from . import credit
from .core import Core
from .people import People
from .ref import Reference
from .util import account_number, add_months, hexes, to_date, ts

ROLE_ACCOUNTS = {  # role → (section, product hint or None for the contract's own kind, take second code)
    "principal": ("loans_individuals", None, False),
    "overdue_principal": ("overdue_loans", None, False),
    "interest": ("accrued_interest", None, False),
    "overdue_interest": ("overdue_interest", None, False),
    "penalty": ("penalties", "general", False),
    "write_off": ("written_off", "written_off", False),
    "write_off_interest": ("written_off", "written_off", True),
    "limit": ("commitments", "credit_line", False),
}


@dataclass
class Tx:
    contracts: list[credit.Contract]
    principal_account: dict[int, str]  # contract → principal account number
    cards: pl.DataFrame  # card_id, contract_id, person, kind
    tables: dict[str, tuple[pl.DataFrame, list[str]]]


def make(rng: np.random.Generator, ref: Reference, people: People, core: Core, snapshot: int, end: int) -> Tx:
    persons = np.flatnonzero(core.customer_id >= 0)
    tables: dict[str, tuple[pl.DataFrame, list[str]]] = {}
    client_id = {int(p): 5_000_000 + i for i, p in enumerate(persons)}
    tables["client"] = (pl.DataFrame({
        "client_id": [client_id[int(p)] for p in persons],
        "core_customer_code": core.customer_code[persons].astype(str),
        "pinfl": people.pinfl[persons],
        "full_name": [f"{people.last_name[p]} {people.first_name[p]} {people.middle_name[p]}" for p in persons],
        "birth_date": [to_date(b) for b in people.birth[persons]],
        "phone": people.phone[persons],
        "risk_level": rng.choice(["low", "medium", "high"], size=len(persons), p=[0.7, 0.25, 0.05]),
        "created_at": [ts(d, 43200) for d in core.customer_open[persons]],
        "_v": core.customer_open[persons].astype(np.int32),
    }), ["client_id"])

    # Contracts: credit lines and microloans run through the engine; debit-card contracts are static.
    contracts: list[credit.Contract] = []
    next_id = 7_000_000
    age = (end - people.birth) / 365.25
    for p in persons:
        opened = int(core.customer_open[p])
        beh = str(people.behaviour[p])
        if 21 <= age[p] <= 65 and people.income[p] >= 2_500_000_00 and rng.random() < 0.32:
            d = opened + int(rng.exponential(90))
            if d <= end:
                limit = int(np.clip(people.income[p] * rng.uniform(1, 3), 2_000_000_00, 30_000_000_00)) // 500_000_00 * 500_000_00
                c = credit.Contract(next_id, int(p), "credit_line", d, beh, limit, 0.49,
                                    transactor=rng.random() < 0.6, utilisation=float(rng.beta(2, 2.5)),
                                    stop=int(rng.integers(1, 8)) if beh == "defaulter" else 10**6)
                credit.run_credit_line(c, rng, end)
                contracts.append(c)
                next_id += 1
        if rng.random() < 0.25:
            d = opened + int(rng.exponential(120))
            for _ in range(2):
                if d > end:
                    break
                term = int(rng.choice([3, 6, 9, 12], p=[0.2, 0.35, 0.2, 0.25]))
                principal = int(np.clip(people.income[p] * rng.uniform(0.5, 2.5), 1_000_000_00, 15_000_000_00)) // 100_000_00 * 100_000_00
                c = credit.Contract(next_id, int(p), "microloan", d, beh, principal, 0.54, term=term,
                                    stop=int(rng.integers(0, term)) if beh == "defaulter" else 10**6)
                credit.run_microloan(c, rng, end)
                contracts.append(c)
                next_id += 1
                closed = [s for s in c.status if s[1] == "closed"]
                if not closed or beh not in ("good", "late") or rng.random() > 0.35:
                    break
                d = closed[0][0] + int(rng.integers(10, 120))

    debit_ids = {int(p): 6_000_000 + i for i, p in enumerate(persons)}
    contract_rows, account_rows, principal_account = [], [], {}
    seq: dict[str, int] = {}
    for p in persons:
        cid = debit_ids[int(p)]
        acc_idx = int(core.card_account[p])
        contract_rows.append((cid, client_id[int(p)], "debit_card", "DC_STD", "active", "UZS", None, None, None, None,
                              core.accounts.number[acc_idx], to_date(core.customer_open[p]), None, int(core.customer_open[p])))
        account_rows.append((40_000_000 + len(account_rows), cid, core.accounts.number[acc_idx], "settlement",
                             core.accounts.balance_account[acc_idx], "UZS", "open", to_date(core.customer_open[p]), None,
                             int(core.customer_open[p])))
    role_account: dict[tuple[int, str], int] = {}
    for c in contracts:
        product = "PL_CARD_49" if c.kind == "credit_line" else f"ML_{c.term}M_54"
        base = (c.contract_id, client_id[c.person], c.kind, product)
        tail = ("UZS", c.amount if c.kind == "credit_line" else None, c.rate * 100,
                c.term or None, c.amount if c.kind == "microloan" else None, None, to_date(c.open_day))
        for d, s in c.status:
            close = to_date(d) if s in ("closed", "written_off") else None
            contract_rows.append((*base, s, *tail, close, d))
        code = core.customer_code[c.person]
        roles = [r for r in credit.ROLES if c.kind == "credit_line" or r != "limit"]
        for role in roles:
            section, hint, second = ROLE_ACCOUNTS[role]
            bal = ref.balance_account(section, hint or c.kind, fx=second)
            seq[code] = seq.get(code, 100) + 1
            number = account_number(bal, "860", code, seq[code])
            aid = 40_000_000 + len(account_rows)
            role_account[(c.contract_id, role)] = aid
            if role == "principal":
                principal_account[c.contract_id] = number
            account_rows.append((aid, c.contract_id, number, role, bal, "UZS", "open", to_date(c.open_day), None, c.open_day))

    contract_cols = ["contract_id", "client_id", "contract_type", "product_code", "status", "currency_code", "credit_limit",
                     "interest_rate", "term_months", "principal_amount", "settlement_account", "open_date", "close_date", "_v"]
    tables["contract"] = (pl.DataFrame(contract_rows, schema=contract_cols, orient="row", infer_schema_length=None), ["contract_id"])
    tables["contract_account"] = (pl.DataFrame(account_rows, schema=[
        "account_id", "contract_id", "account_number", "account_role", "balance_account", "currency_code", "status",
        "open_date", "close_date", "_v"], orient="row", infer_schema_length=None), ["account_id"])

    # Turnover: postings aggregated per account and day, balances by running sum.
    rows = [(role_account[(c.contract_id, role)], d, dr, cr) for c in contracts for d, role, dr, cr in c.postings]
    post = pl.DataFrame(rows, schema=["account_id", "_v", "debit_turnover", "credit_turnover"], orient="row", infer_schema_length=None)
    turnover = (post.group_by("account_id", "_v").agg(pl.col("debit_turnover").sum(), pl.col("credit_turnover").sum())
                .filter(pl.col("_v") <= end).sort("account_id", "_v")
                .with_columns((pl.col("debit_turnover") - pl.col("credit_turnover")).cum_sum().over("account_id").alias("closing_balance"))
                .with_columns((pl.col("closing_balance") - pl.col("debit_turnover") + pl.col("credit_turnover")).alias("opening_balance"),
                              pl.col("_v").map_elements(to_date, return_dtype=pl.Date).alias("oper_day"))
                .select("account_id", "oper_day", "opening_balance", "debit_turnover", "credit_turnover", "closing_balance", "_v"))
    tables["account_turnover"] = (turnover, ["account_id", "oper_day"])

    sched = []
    for c in contracts:
        for d, line, paid, unpaid, paid_day in c.line_versions:
            ln = c.schedule[line]
            sched.append((c.contract_id * 100 + line, c.contract_id, 1, ln["kind"], to_date(ln["due"]), ln["amount"],
                          paid, unpaid, to_date(paid_day) if paid_day else None, d))
    tables["payment_schedule"] = (pl.DataFrame(sched, schema=[
        "schedule_line_id", "contract_id", "schedule_revision", "debt_kind", "due_date", "scheduled_amount", "paid_amount",
        "unpaid_amount", "last_paid_date", "_v"], orient="row", infer_schema_length=None), ["schedule_line_id"])

    cyc = []
    for c in contracts:
        for d, i, paid, overdue_start, last_pay in c.cycle_versions:
            y = c.cycles[i]
            cyc.append((c.contract_id, to_date(y["statement"]), to_date(y["start"]), to_date(y["due"]), to_date(y["due"]),
                        y["balance"], y["min"], y["used"], paid, to_date(overdue_start) if overdue_start else None,
                        to_date(last_pay) if last_pay else None, d))
    tables["credit_line_cycle"] = (pl.DataFrame(cyc, schema=[
        "contract_id", "statement_date", "cycle_start_date", "due_date", "grace_end_date", "statement_balance",
        "min_payment", "used_limit", "paid_amount", "overdue_start_date", "last_payment_date", "_v"], orient="row", infer_schema_length=None),
        ["contract_id", "statement_date"])

    delq = []
    for c in contracts:
        prev = "current"
        for d, state, dpd in credit.states(c, end):
            delq.append((c.contract_id, to_date(d), state, prev, dpd, ts(d, 82800), d))
            prev = state
    tables["delinquency_history"] = (pl.DataFrame(delq, schema=[
        "contract_id", "effective_date", "state", "previous_state", "days_past_due", "recorded_at", "_v"], orient="row", infer_schema_length=None),
        ["contract_id", "effective_date"])

    cards = _cards(rng, persons, debit_ids, client_id, core, contracts, end)
    tables["card"] = (cards.drop("person", "kind"), ["card_id"])
    tables["mcc"] = (ref.mcc.select("mcc", "description", "category_group", pl.col("is_cash_like") == "true",
                                    pl.col("is_high_risk") == "true").with_columns(pl.lit(snapshot, dtype=pl.Int32).alias("_v")),
                     ["mcc"])
    for name, (frame, key) in tables.items():
        tables[name] = (frame.with_columns(pl.col("_v").cast(pl.Int32)), key)
    return Tx(contracts=contracts, principal_account=principal_account, cards=cards, tables=tables)


def _cards(rng: np.random.Generator, persons: np.ndarray, debit_ids: dict, client_id: dict, core: Core,
           contracts: list[credit.Contract], end: int) -> pl.DataFrame:
    rows = []
    owners = [(debit_ids[int(p)], int(p), int(core.customer_open[p]), "debit") for p in persons]
    owners += [(c.contract_id, c.person, c.open_day, "credit") for c in contracts if c.kind == "credit_line"]
    for contract_id, p, opened, kind in owners:
        n = 1 + int(kind == "debit" and rng.random() < 0.1)
        for j in range(n):
            humo = rng.random() < 0.55
            bin_ = f"9860{rng.integers(10, 40)}" if humo else f"8600{rng.integers(10, 60)}"
            product = "sticker" if j else ("virtual" if kind == "debit" and rng.random() < 0.35 else "plastic")
            rows.append((8_000_000 + len(rows), contract_id, client_id[p], product, "HUMO" if humo else "UZCARD", "active",
                         f"{bin_}******{rng.integers(0, 10000):04d}", ts(opened, 43200), to_date(add_months(opened, 48)),
                         p, kind, opened))
    frame = pl.DataFrame(rows, schema=["card_id", "contract_id", "client_id", "product_type", "network", "status",
                                       "masked_pan", "issued_at", "expiry_date", "person", "kind", "_v"], orient="row", infer_schema_length=None)
    return frame.with_columns(pl.Series("pan_hash", hexes(rng, frame.height, 64)))
