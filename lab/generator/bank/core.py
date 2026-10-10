"""iabs: core banking — dictionaries, customers, accounts, deposits, exchange rates, operating days."""

from dataclasses import dataclass, field

import numpy as np
import polars as pl

from .people import People
from .ref import Reference
from .util import account_number, add_months, day, to_date

BANK_CODE = "01099"
OTHER_BANKS = ["00014", "00401", "00873", "01036", "00440", "00084", "00982", "01095"]
COMPANY_WORDS = ["Sharq", "Ipak Yo'li", "Navro'z", "Baraka", "Oltin Vodiy", "Zarafshon", "Turon", "Yangi Asr", "Orient",
                 "Afrosiyob", "Registon", "Buxoro", "Farg'ona", "Chirchiq", "Grand", "Mega", "Silk Road", "Bunyodkor"]
COMPANY_KINDS = ["Savdo", "Trans", "Qurilish", "Textile", "Agro", "Pharm", "Logistics", "Food", "Tech", "Service",
                 "Invest", "Energy", "Print", "Med", "Auto"]
LEGAL_FORMS = ["MChJ", "AJ", "XK", "OK"]
OKED = ["47110", "46900", "41200", "13100", "01110", "21200", "49410", "10710", "62010", "96090", "64990", "35110"]


@dataclass
class Accounts:
    """All iabs accounts, indexed 0..n-1; balances simulated in daily.py."""

    account_id: list[int] = field(default_factory=list)
    number: list[str] = field(default_factory=list)
    balance_account: list[str] = field(default_factory=list)
    currency: list[str] = field(default_factory=list)  # alpha code
    customer_code: list[str] = field(default_factory=list)
    kind: list[str] = field(default_factory=list)  # card, current_fx, deposit, settlement
    open_day: list[int] = field(default_factory=list)
    close_day: list[int | None] = field(default_factory=list)
    opening: list[int] = field(default_factory=list)  # balance at snapshot (tiyin), 0 if opened later
    seq: dict[str, int] = field(default_factory=dict)

    def add(self, bal: str, ccy_alpha: str, ccy_num: str, customer: str, kind: str, opened: int, opening: int = 0) -> int:
        self.seq[customer] = self.seq.get(customer, 0) + 1
        self.account_id.append(10_000_000 + len(self.account_id))
        self.number.append(account_number(bal, ccy_num, customer, self.seq[customer]))
        self.balance_account.append(bal)
        self.currency.append(ccy_alpha)
        self.customer_code.append(customer)
        self.kind.append(kind)
        self.open_day.append(opened)
        self.close_day.append(None)
        self.opening.append(opening)
        return len(self.account_id) - 1


@dataclass
class Core:
    customer_id: np.ndarray  # per person, -1 if never a customer
    customer_code: np.ndarray  # per person
    customer_open: np.ndarray  # per person, day
    card_account: np.ndarray  # per person → account index (-1)
    companies: pl.DataFrame
    company_account: np.ndarray  # company index → account index
    company_employees: dict[int, np.ndarray]
    accounts: Accounts
    deposits: list[dict]
    rates: dict[str, np.ndarray]  # alpha → rate per day index from rate_start
    rate_start: int
    numeric: dict[str, str]


def exchange_rates(rng: np.random.Generator, ref: Reference, start: int, end: int) -> tuple[pl.DataFrame, dict]:
    days = np.arange(start, end + 1)
    rows, series = [], {}
    for r in ref.currencies.iter_rows(named=True):
        code, vol = r["currency_code"], float(r["daily_volatility_pct"]) / 100
        if code == "UZS":
            series[code] = np.ones(len(days))
            continue
        walk = np.exp(np.cumsum(rng.normal(0.00012, vol, size=len(days))))
        rate = float(r["start_rate_uzs"]) * walk / walk[-1] * (1 + rng.normal(0, 0.002))
        series[code] = np.round(rate, 2)
        nominal = 1
        rows += [(r["numeric_code"], code, to_date(d), float(x), nominal, int(d)) for d, x in zip(days, series[code], strict=True)]
    frame = pl.DataFrame(rows, schema=["currency_numeric", "currency_code", "rate_date", "rate", "nominal", "_v"],
                         orient="row", infer_schema_length=None).with_columns(pl.col("_v").cast(pl.Int32))
    return frame, series


def dictionaries(ref: Reference, start: int, end: int, snapshot: int) -> dict[str, tuple[pl.DataFrame, list[str]]]:
    holidays = {day(to_date(0).fromisoformat(d)) for d in ref.holidays.filter(pl.col("is_non_working") == "true")["holiday_date"]}
    days = np.arange(start, end + 1)
    operating = pl.DataFrame({
        "oper_day": [to_date(d) for d in days],
        "prev_oper_day": [to_date(d - 1) for d in days],
        "next_oper_day": [to_date(d + 1) for d in days],
        "is_holiday": [int(d) in holidays for d in days],
        "is_weekend": [to_date(d).weekday() >= 5 for d in days],
        "day_status": "closed",
        "_v": days.astype(np.int32),
    })
    at0 = lambda f: f.with_columns(pl.lit(snapshot, dtype=pl.Int32).alias("_v"))
    regions = ref.regions.select("region_code", "region_name")
    branches = pl.DataFrame({
        "branch_code": [BANK_CODE] + [f"0{i + 2:02d}{r[-2:]}" for i, r in enumerate(ref.regions["region_code"])],
        "branch_name": ["Head office (digital)"] + [f"{n} regional office" for n in ref.regions["region_name"]],
        "region_code": ["1726"] + ref.regions["region_code"].to_list(),
    })
    currency = ref.currencies.select(pl.col("numeric_code").alias("currency_numeric"),
                                     "currency_code", pl.col("name").alias("currency_name"), "minor_units")
    chart = ref.balance_accounts.rename({"class": "account_class"}).with_columns(pl.col("is_contra") == "true")
    return {
        "operating_day": (operating, ["oper_day"]),
        "region": (at0(regions), ["region_code"]),
        "district": (at0(ref.districts.with_columns(pl.col("is_city") == "1")), ["district_code"]),
        "branch": (at0(branches), ["branch_code"]),
        "currency": (at0(currency), ["currency_numeric"]),
        "balance_account": (at0(chart.drop("product_hint")), ["code"]),
    }


def make(rng: np.random.Generator, ref: Reference, people: People, kyc_day_person: np.ndarray,
         start: int, snapshot: int, end: int, rate_frame_series: tuple) -> tuple[Core, dict[str, tuple[pl.DataFrame, list[str]]]]:
    tables: dict[str, tuple[pl.DataFrame, list[str]]] = {}
    numeric = dict(zip(ref.currencies["currency_code"], ref.currencies["numeric_code"], strict=True))
    rate_frame, rates = rate_frame_series

    # Customers: persons who passed onboarding KYC, in order of becoming customers.
    is_cust = kyc_day_person >= 0
    order = np.flatnonzero(is_cust)[np.argsort(kyc_day_person[is_cust], kind="stable")]
    customer_id = np.full(people.n, -1, dtype=np.int64)
    customer_code = np.full(people.n, "", dtype=object)
    customer_id[order] = 1_000_000 + np.arange(len(order))
    customer_code[order] = [f"{2_000_000 + i:08d}" for i in range(len(order))]
    open_day = kyc_day_person.copy()

    # Companies: employers (salary payers) and payees; customers since before the history window.
    n_comp = max(20, people.n // 250)
    comp_code = [f"{9_000_000 + i:08d}" for i in range(n_comp)]
    comp_open = start - rng.integers(30, 2000, size=n_comp)
    directors = rng.integers(0, people.n, size=n_comp)
    companies = pl.DataFrame({
        "customer_code": comp_code,
        "company_name": [f"{rng.choice(COMPANY_WORDS)} {rng.choice(COMPANY_KINDS)} {rng.choice(LEGAL_FORMS)}" for _ in range(n_comp)],
        "registration_date": [to_date(d - rng.integers(0, 3000)) for d in comp_open],
        "oked_code": rng.choice(OKED, n_comp),
        "legal_form": rng.choice(LEGAL_FORMS, n_comp),
        "director_name": [f"{people.last_name[p]} {people.first_name[p]} {people.middle_name[p]}" for p in directors],
        "director_pinfl": people.pinfl[directors],
    })
    employer = rng.integers(0, n_comp, size=people.n)

    cust_rows = {
        "customer_id": np.concatenate([customer_id[order], 900_000 + np.arange(n_comp)]),
        "customer_code": np.concatenate([customer_code[order], comp_code]).astype(str),
        "customer_type": ["individual"] * len(order) + ["company"] * n_comp,
        "tax_id": pl.Series(dtype=pl.Utf8, values=np.concatenate([np.where(rng.random(len(order)) < 0.6, rng.integers(400_000_000, 699_999_999, len(order)).astype(str), None),
                                  rng.integers(200_000_000, 309_999_999, n_comp).astype(str)]).tolist()),
        "branch_code": np.concatenate([[f"0{list(ref.regions['region_code']).index(r) + 2:02d}{r[-2:]}" for r in people.region[order]],
                                       [BANK_CODE] * n_comp]),
        "status": "active",
        "open_date": [to_date(d) for d in np.concatenate([open_day[order], comp_open])],
        "close_date": pl.Series([None] * (len(order) + n_comp), dtype=pl.Date),
        "_v": np.concatenate([open_day[order], np.full(n_comp, start)]).astype(np.int32),
    }
    customers = pl.DataFrame(cust_rows).with_columns(pl.col("open_date").cast(pl.Utf8).alias("updated_at"))
    tables["customer"] = (customers, ["customer_id"])

    p = order
    tables["customer_individual"] = (pl.DataFrame({
        "customer_code": customer_code[p].astype(str),
        "pinfl": people.pinfl[p],
        "last_name": people.last_name[p],
        "first_name": people.first_name[p],
        "middle_name": people.middle_name[p],
        "birth_date": [to_date(b) for b in people.birth[p]],
        "gender": people.gender[p],
        "passport_series": people.passport_series[p],
        "passport_number": people.passport_number[p],
        "passport_issued": [to_date(b) for b in people.passport_issued[p]],
        "district_code": people.district[p],
        "address": [f"{rng.choice(['Amir Temur', 'Navoiy', 'Mustaqillik', 'Bobur', 'Uzbekistan', 'Shota Rustaveli', 'Furqat', 'Bunyodkor'])} "
                    f"ko'chasi, {rng.integers(1, 200)}-uy, {rng.integers(1, 120)}-xonadon" for _ in p],
        "phone": people.phone[p],
        "monthly_income": people.income[p],
        "_v": open_day[p].astype(np.int32),
    }), ["customer_code"])
    tables["customer_company"] = (companies.with_columns(pl.lit(start, dtype=pl.Int32).alias("_v")), ["customer_code"])

    # Accounts.
    acc = Accounts()
    card_account = np.full(people.n, -1, dtype=np.int64)
    card_bal = ref.balance_account("card_accounts", "card")
    for i in p:
        opening = 0
        if open_day[i] <= snapshot:
            f = 0.02 if people.behaviour[i] == "dormant" else rng.uniform(0.15, 1.1)
            opening = int(people.income[i] * f) // 100 * 100
        card_account[i] = acc.add(card_bal, "UZS", "860", customer_code[i], "card", int(open_day[i]), opening)
    settle_bal = "20200"
    company_account = np.array([acc.add(settle_bal, "UZS", "860", c, "settlement", int(d), int(rng.integers(5, 50) * 10**10))
                                for c, d in zip(comp_code, comp_open, strict=True)])
    employees = {c: np.flatnonzero((employer == c) & people.employed & is_cust) for c in range(n_comp)}

    # Term deposits: ~8% of customers; 12% in USD with a USD current account for interest.
    deposits = []
    term_bal_uzs = ref.balance_account("deposits_term", "deposit_term")
    term_bal_fx = ref.balance_account("deposits_term", "deposit_term", fx=True)
    fx_current = ref.balance_account("deposits_demand", "deposit_demand", fx=True)
    who = p[rng.random(len(p)) < 0.08]
    for i in who:
        opened = int(open_day[i] + rng.integers(0, 400))
        if opened > end:
            continue
        usd = rng.random() < 0.12
        term = int(rng.choice([6, 12, 18], p=[0.3, 0.5, 0.2]))
        rate = (rng.choice([4.0, 5.0, 6.0]) if usd else {6: 20.0, 12: 22.0, 18: 23.0}[term]) + rng.choice([0, 0.5])
        if usd:
            amount = int(people.income[i] * rng.uniform(2, 12) / rates["USD"][-1]) // 10000 * 10000
        else:
            amount = int(people.income[i] * rng.uniform(2, 20)) // 10_000_000 * 10_000_000
        amount = max(amount, 100_00 if usd else 1_000_000_00)
        planned_end = add_months(opened, term, 31)
        early = rng.random() < 0.05
        actual_end = int(opened + rng.integers(30, max(31, planned_end - opened))) if early else planned_end
        ccy = "USD" if usd else "UZS"
        dep_acc = acc.add(term_bal_fx if usd else term_bal_uzs, ccy, numeric[ccy], customer_code[i], "deposit", opened,
                          amount if opened <= snapshot else 0)
        interest_acc = int(card_account[i])
        if usd:
            interest_acc = acc.add(fx_current, "USD", "840", customer_code[i], "current_fx", opened, 0)
        if actual_end <= end:
            acc.close_day[dep_acc] = actual_end
        deposits.append({"deposit_id": 3_000_000 + len(deposits), "person": int(i), "account": dep_acc,
                         "interest_account": interest_acc, "currency": ccy, "amount": amount, "rate": float(rate),
                         "term": term, "start": opened, "planned_end": planned_end, "actual_end": actual_end,
                         "early": early})

    tables["deposit_contract"] = (_deposit_versions(deposits, customer_code, acc, end), ["deposit_id"])
    tables["exchange_rate"] = (rate_frame, ["currency_code", "rate_date"])
    core = Core(customer_id=customer_id, customer_code=customer_code, customer_open=open_day, card_account=card_account,
                companies=companies, company_account=company_account, company_employees=employees, accounts=acc,
                deposits=deposits, rates=rates, rate_start=start, numeric=numeric)
    return core, tables


def _deposit_versions(deposits: list[dict], customer_code: np.ndarray, acc: Accounts, end: int) -> pl.DataFrame:
    rows = []
    for d in deposits:
        base = (d["deposit_id"], f"TD-{d['deposit_id']}", customer_code[d["person"]],
                f"term_{d['term']}m", d["currency"], d["amount"], d["rate"], to_date(d["start"]),
                to_date(d["planned_end"]), acc.number[d["account"]])
        rows.append((*base, None, "active", int(d["start"])))
        if d["actual_end"] <= end:
            rows.append((*base, to_date(d["actual_end"]), "closed_early" if d["early"] else "closed", int(d["actual_end"])))
    return pl.DataFrame(rows, schema=["deposit_id", "contract_number", "customer_code", "deposit_type", "currency_code",
                                      "amount", "interest_rate", "start_date", "planned_end_date", "account_number",
                                      "actual_end_date", "state", "_v"], orient="row", infer_schema_length=None).with_columns(pl.col("_v").cast(pl.Int32))


def accounts_frame(acc: Accounts, end: int) -> pl.DataFrame:
    n = len(acc.account_id)
    base = pl.DataFrame({
        "account_id": acc.account_id,
        "account_number": acc.number,
        "balance_account": acc.balance_account,
        "currency_code": acc.currency,
        "customer_code": acc.customer_code,
        "account_type": acc.kind,
        "status": "open",
        "open_date": [to_date(d) for d in acc.open_day],
        "close_date": pl.Series([None] * n, dtype=pl.Date),
        "_v": pl.Series(acc.open_day, dtype=pl.Int32),
    })
    closed = [i for i, c in enumerate(acc.close_day) if c is not None and c <= end]
    v2 = base[closed].with_columns(
        pl.lit("closed").alias("status"),
        pl.Series([to_date(acc.close_day[i]) for i in closed], dtype=pl.Date).alias("close_date"),
        pl.Series([acc.close_day[i] for i in closed], dtype=pl.Int32).alias("_v"),
    )
    return pl.concat([base, v2])

