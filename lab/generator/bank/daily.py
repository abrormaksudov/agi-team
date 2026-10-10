"""The simulated operating days: iabs account movements, payment documents, card transactions.

Order within a day: credits (salaries, incoming transfers, deposit flows, loan disbursements), then
debits (loan repayments, outgoing transfers), then card purchases approved while the balance lasts.
Balances never go negative; a repayment the card account cannot cover is paid from another bank's card.
"""

import numpy as np
import polars as pl

from .core import BANK_CODE, OTHER_BANKS, Core
from .people import People
from .ref import Reference
from .tx import Tx
from .util import daytime_seconds, to_date, ts


class Day:
    def __init__(self, n_acc: int) -> None:
        self.debit = np.zeros(n_acc, dtype=np.int64)
        self.credit = np.zeros(n_acc, dtype=np.int64)
        self.docs: list[dict] = []


def _external_account(rng: np.random.Generator, n: int) -> np.ndarray:
    return np.array([f"20208000{x:012d}" for x in rng.integers(0, 10**12, size=n)])


def run(rng: np.random.Generator, ref: Reference, people: People, core: Core, tx: Tx, snapshot: int,
        end: int) -> dict[str, tuple[pl.DataFrame, list[str]]]:
    acc = core.accounts
    n_acc = len(acc.account_id)
    balance = np.array(acc.opening, dtype=np.int64)
    numbers = np.array(acc.number, dtype=object)
    usd = np.array([c == "USD" for c in acc.currency])
    open_day = np.array(acc.open_day)
    names = np.char.add(np.char.add(people.last_name.astype(str), " "), people.first_name.astype(str))
    cust_people = np.flatnonzero(core.customer_id >= 0)
    card_acc = core.card_account
    comp_names = core.companies["company_name"].to_numpy()

    mcc = ref.mcc
    mcc_code = mcc["mcc"].to_numpy()
    mcc_w = mcc["spend_weight"].cast(pl.Float64).to_numpy()
    mcc_w = mcc_w / mcc_w.sum()
    mcc_avg = mcc["avg_amount_uzs"].cast(pl.Float64).to_numpy()
    mcc_group = mcc["category_group"].to_numpy()
    mcc_cash = (mcc["is_cash_like"] == "true").to_numpy()

    debit_cards = tx.cards.filter(pl.col("kind") == "debit").unique("contract_id", keep="first")
    dc_card = debit_cards["card_id"].to_numpy()
    dc_contract = debit_cards["contract_id"].to_numpy()
    dc_person = debit_cards["person"].to_numpy()
    dc_open = debit_cards["_v"].to_numpy()
    credit_cards = tx.cards.filter(pl.col("kind") == "credit").unique("contract_id", keep="first")
    cc_card = dict(zip(credit_cards["contract_id"].to_list(), credit_cards["card_id"].to_list(), strict=True))

    repay_by_day: dict[int, list] = {}
    disburse_by_day: dict[int, list] = {}
    draws_by_day: dict[int, list] = {}
    for c in tx.contracts:
        for d, x in c.repayments:
            if snapshot < d <= end:
                repay_by_day.setdefault(d, []).append((c.person, x, c.contract_id))
        if c.kind == "microloan" and snapshot < c.open_day <= end:
            disburse_by_day.setdefault(c.open_day, []).append((c.person, c.amount, c.contract_id))
        if c.kind == "credit_line":
            for d, x in c.draws:
                if snapshot < d <= end:
                    draws_by_day.setdefault(d, []).append((c.contract_id, x))

    balances, docs, txns = [], [], []
    # Snapshot: one balance row per account open on the snapshot day.
    at0 = np.flatnonzero(open_day <= snapshot)
    balances.append(pl.DataFrame({"account_id": np.array(acc.account_id)[at0], "_v": np.full(len(at0), snapshot),
                                  "opening_balance": balance[at0], "debit_turnover": 0, "credit_turnover": 0,
                                  "closing_balance": balance[at0]}))
    doc_id, txn_id = 50_000_000, 900_000_000
    for d in range(snapshot + 1, end + 1):
        day = Day(n_acc)
        dom, weekend = to_date(d).day, to_date(d).weekday() >= 5
        rate_usd = core.rates["USD"][d - core.rate_start]

        def doc(payer, payer_bank, payer_name, payee, payee_bank, payee_name, amount, purpose, ccy="UZS", day=day):
            day.docs.append({"payer_account": payer, "payer_bank_code": payer_bank, "payer_name": payer_name,
                             "payee_account": payee, "payee_bank_code": payee_bank, "payee_name": payee_name,
                             "amount": int(amount), "currency_code": ccy, "purpose": purpose})

        # Deposits opened today, funded from another bank; interest monthly; maturity back to the customer.
        for dep in core.deposits:
            a, p = dep["account"], dep["person"]
            if dep["start"] == d:
                day.credit[a] += dep["amount"]
                doc(_external_account(rng, 1)[0], rng.choice(OTHER_BANKS), names[p], numbers[a], BANK_CODE, names[p],
                    dep["amount"], f"Term deposit funding, contract TD-{dep['deposit_id']}", dep["currency"])
            elif dep["start"] < d < dep["actual_end"] and to_date(d).day == to_date(dep["start"]).day:
                day.credit[dep["interest_account"]] += round(dep["amount"] * dep["rate"] / 100 / 12)
            if dep["actual_end"] == d and dep["start"] < d:
                day.debit[a] += dep["amount"]
                day.credit[dep["interest_account"]] += dep["amount"]

        # Salaries from employer settlement accounts; companies funded from other banks when short.
        for comp, staff in core.company_employees.items():
            staff = staff[(people.salary_day[staff] == dom) & (core.customer_open[staff] < d)]
            if not len(staff):
                continue
            pay = (people.income[staff] * rng.uniform(0.97, 1.03, size=len(staff))).astype(np.int64) // 100 * 100
            ca = core.company_account[comp]
            total = int(pay.sum())
            if balance[ca] + day.credit[ca] - day.debit[ca] < total:
                top = int(total * 1.5)
                day.credit[ca] += top
                doc(_external_account(rng, 1)[0], rng.choice(OTHER_BANKS), "Contract payments", numbers[ca], BANK_CODE,
                    comp_names[comp], top, "Payment for goods and services under contract")
            day.debit[ca] += total
            np.add.at(day.credit, card_acc[staff], pay)
            for p, x in zip(staff, pay, strict=True):
                doc(numbers[ca], BANK_CODE, comp_names[comp], numbers[card_acc[p]], BANK_CODE, names[p], x,
                    f"Salary for {to_date(d):%B %Y}")

        # Self-employed and others: incoming transfers from other banks.
        others = cust_people[(~people.employed[cust_people]) & (core.customer_open[cust_people] < d)]
        got = others[rng.random(len(others)) < 0.1]
        amounts = (people.income[got] * rng.uniform(0.15, 0.5, size=len(got))).astype(np.int64) // 100_00 * 100_00
        np.add.at(day.credit, card_acc[got], amounts)
        for p, x, ext in zip(got, amounts, _external_account(rng, len(got)), strict=True):
            doc(ext, rng.choice(OTHER_BANKS), names[rng.integers(0, people.n)], numbers[card_acc[p]], BANK_CODE, names[p],
                x, "P2P transfer")

        for p, x, cid in disburse_by_day.get(d, []):
            day.credit[card_acc[p]] += x
            doc(tx.principal_account[cid], BANK_CODE, "Microloan disbursement", numbers[card_acc[p]], BANK_CODE, names[p],
                x, f"Microloan disbursement under contract {cid}")

        avail = balance + day.credit - day.debit
        for p, x, cid in repay_by_day.get(d, []):
            a = card_acc[p]
            if rng.random() < 0.3:
                continue  # paid from another bank's card through a payment app
            if avail[a] < x:
                top = int(x - avail[a])
                avail[a] += top
                day.credit[a] += top
                doc(_external_account(rng, 1)[0], rng.choice(OTHER_BANKS), names[p], numbers[a], BANK_CODE, names[p], top,
                    "Own funds transfer")
            if avail[a] >= x:
                avail[a] -= x
                day.debit[a] += x
                doc(numbers[a], BANK_CODE, names[p], tx.principal_account[cid], BANK_CODE, names[p], x,
                    f"Repayment under loan contract {cid}")

        # Outgoing transfers and utility payments.
        active = cust_people[(core.customer_open[cust_people] < d) & (rng.random(len(cust_people)) < 0.05)]
        a_idx = card_acc[active]
        out_amt = (avail[a_idx] * rng.uniform(0.05, 0.3, size=len(active))).astype(np.int64) // 1000_00 * 1000_00
        ok = out_amt > 0
        for p, a, x, ext in zip(active[ok], a_idx[ok], out_amt[ok], _external_account(rng, int(ok.sum())), strict=True):
            avail[a] -= x
            day.debit[a] += x
            purpose = rng.choice(["P2P transfer", "Utility payment", "Mobile top-up", "Tuition payment"], p=[0.6, 0.2, 0.15, 0.05])
            doc(numbers[a], BANK_CODE, names[p], ext, rng.choice(OTHER_BANKS), names[rng.integers(0, people.n)], x, purpose)

        # Debit-card purchases, approved while the balance lasts.
        live = np.flatnonzero(dc_open < d)
        act = people.activity[dc_person[live]] * (1.1 if weekend else 1.0)
        on = live[rng.random(len(live)) < act]
        k = 1 + rng.poisson(0.5, size=len(on))
        idx = np.repeat(on, k)
        m = rng.choice(len(mcc_code), size=len(idx), p=mcc_w)
        wealth = np.clip(people.income[dc_person[idx]] / 4_500_000_00, 0.35, 3.0) ** 0.6
        amount = (np.exp(rng.normal(np.log(mcc_avg[m] * wealth * 0.7), 0.6)) // 100 * 100 * 100).astype(np.int64)
        sec = daytime_seconds(rng, len(idx))
        frame = pl.DataFrame({"i": idx, "m": m, "amount": amount, "sec": sec,
                              "acc": card_acc[dc_person[idx]]}).sort("acc", "sec")
        frame = frame.with_columns(pl.col("amount").cum_sum().over("acc").alias("cum"))
        approved = frame["cum"].to_numpy() <= avail[frame["acc"].to_numpy()]
        fa = frame["acc"].to_numpy()
        np.add.at(day.debit, fa[approved], frame["amount"].to_numpy()[approved])
        tech = rng.random(frame.height) < 0.012
        status = np.where(approved & ~tech, "approved", "declined")
        reason = np.where(status == "approved", None, np.where(approved, rng.choice(["do_not_honor", "wrong_pin", "suspected_fraud"],
                                                                                   size=frame.height, p=[0.6, 0.3, 0.1]), "insufficient_funds"))
        # technical declines did not move money: give it back
        np.add.at(day.debit, fa[approved & tech], -frame["amount"].to_numpy()[approved & tech])
        fi, fm = frame["i"].to_numpy(), frame["m"].to_numpy()
        txns.append(_txn_frame(rng, txn_id, d, dc_card[fi], dc_contract[fi], mcc_code[fm], mcc_group[fm], mcc_cash[fm],
                               frame["amount"].to_numpy(), frame["sec"].to_numpy(), status, reason, rate_usd))
        txn_id += frame.height

        # Credit-line purchases: the day's draws split into transactions.
        draws = draws_by_day.get(d, [])
        if draws:
            cids, cards, amts = [], [], []
            for cid, x in draws:
                parts = 1 + min(int(rng.poisson(1.2)), 4)
                split = (rng.dirichlet(np.ones(parts)) * x).astype(np.int64) // 100 * 100
                split[-1] = x - split[:-1].sum()
                cids += [cid] * parts
                cards += [cc_card[cid]] * parts
                amts += split.tolist()
            m = rng.choice(len(mcc_code), size=len(amts), p=mcc_w)
            txns.append(_txn_frame(rng, txn_id, d, np.array(cards), np.array(cids), mcc_code[m], mcc_group[m], mcc_cash[m],
                                   np.array(amts, dtype=np.int64), daytime_seconds(rng, len(amts)),
                                   np.full(len(amts), "approved"), np.full(len(amts), None, dtype=object), rate_usd))
            txn_id += len(amts)

        moved = np.flatnonzero((day.debit != 0) | (day.credit != 0))
        opening = balance[moved]
        balance += day.credit - day.debit
        assert (balance[~usd] >= 0).all(), f"negative balance on {to_date(d)}"
        balances.append(pl.DataFrame({"account_id": np.array(acc.account_id)[moved], "_v": np.full(len(moved), d),
                                      "opening_balance": opening, "debit_turnover": day.debit[moved],
                                      "credit_turnover": day.credit[moved], "closing_balance": balance[moved]}))
        if day.docs:
            f = pl.DataFrame(day.docs)
            sec = np.sort(daytime_seconds(rng, f.height))
            docs.append(f.with_columns(
                pl.Series("document_id", np.arange(doc_id, doc_id + f.height)),
                pl.lit(to_date(d)).alias("document_date"),
                pl.lit(to_date(d)).alias("oper_day"),
                pl.lit("executed").alias("state"),
                pl.Series("created_at", [ts(d, s) for s in sec]),
                pl.lit(d).alias("_v"),
            ))
            doc_id += f.height

    bal = pl.concat(balances, how="vertical_relaxed")
    rate = core.rates["USD"]
    fx = set(np.array(acc.account_id)[usd].tolist())
    bal = bal.with_columns(
        pl.col("_v").map_elements(to_date, return_dtype=pl.Date).alias("oper_day"),
        pl.when(pl.col("account_id").is_in(list(fx)))
        .then((pl.col("closing_balance") * pl.col("_v").map_elements(lambda v: float(rate[v - core.rate_start]),
                                                                     return_dtype=pl.Float64)).round(0).cast(pl.Int64))
        .otherwise(pl.col("closing_balance")).alias("closing_balance_eqv"),
    ).select("account_id", "oper_day", "opening_balance", "debit_turnover", "credit_turnover", "closing_balance",
             "closing_balance_eqv", "_v")
    out = {
        "account_balance": (bal.with_columns(pl.col("_v").cast(pl.Int32)), ["account_id", "oper_day"]),
        "card_transaction": (pl.concat(txns, how="vertical_relaxed").with_columns(pl.col("_v").cast(pl.Int32)), ["transaction_id"]),
    }
    if docs:
        doc_frame = pl.concat(docs, how="vertical_relaxed").select("document_id", "document_date", "oper_day", "payer_account", "payer_bank_code",
                                           "payer_name", "payee_account", "payee_bank_code", "payee_name", "amount",
                                           "currency_code", "purpose", "state", "created_at", "_v")
        out["payment_document"] = (doc_frame.with_columns(pl.col("_v").cast(pl.Int32)), ["document_id"])
    return out


def _txn_frame(rng, start, d, card, contract, mcc, group, cash, amount_uzs, sec, status, reason, rate_usd) -> pl.DataFrame:
    n = len(card)
    ecom_group = np.isin(group, ["online_retail", "digital", "travel", "transport"])
    channel = np.where(cash, "atm", np.where(ecom_group & (rng.random(n) < 0.75), "ecom",
                                            np.where(rng.random(n) < 0.55, "contactless", "pos")))
    in_usd = (channel == "ecom") & (rng.random(n) < 0.04)
    amount = np.where(in_usd, np.round(amount_uzs / rate_usd).astype(np.int64), amount_uzs)
    kind = np.where(cash & (mcc == "6011"), "cash_withdrawal", np.where(np.isin(mcc, ["4829", "6012"]), "transfer", "purchase"))
    return pl.DataFrame({
        "transaction_id": np.arange(start, start + n),
        "card_id": card,
        "contract_id": contract,
        "oper_day": [to_date(d)] * n,
        "registered_at": [ts(d, s) for s in sec],
        "transaction_kind": kind,
        "channel": channel,
        "mcc": mcc,
        "amount": amount,
        "currency_code": np.where(in_usd, "USD", "UZS"),
        "amount_uzs": amount_uzs,
        "status": status,
        "decline_reason": pl.Series(reason.tolist(), dtype=pl.Utf8),
        "rrn": [f"{x:012d}" for x in rng.integers(0, 10**12, size=n)],
        "_v": np.full(n, d, dtype=np.int32),
    })
