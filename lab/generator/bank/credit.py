"""tranzaxis: retail credit engine — credit lines and microloans, simulated contract by contract.

Each contract posts to its role accounts (principal, interest, overdue principal, overdue interest, penalty,
write-off, limit). Unpaid dues become overdue slices dated by their due date; payments clear the oldest
first (FIFO), so days past due are always derivable from postings. A contract is written off when its
oldest unpaid slice is 361 days old. Events are processed in day order.
"""

from dataclasses import dataclass, field
from itertools import pairwise

import numpy as np

from .util import add_months, day, to_date

PENALTY_DAILY = 0.0005
MIN_PAY_FLOOR = 100_000_00  # 100,000 UZS in tiyin
WRITE_OFF_DPD = 361
STATES = [(1, "dpd_1_30"), (31, "dpd_31_60"), (61, "dpd_61_90"), (91, "dpd_91_180"), (181, "dpd_181_360")]
ROLES = ("principal", "interest", "overdue_principal", "overdue_interest", "penalty", "write_off",
         "write_off_interest", "limit")


@dataclass
class Contract:
    contract_id: int
    person: int
    kind: str  # credit_line | microloan
    open_day: int
    behaviour: str
    amount: int  # limit or principal, tiyin
    rate: float  # annual, fraction
    term: int = 0  # months (microloan)
    transactor: bool = False
    utilisation: float = 0.0
    stop: int = 10**6  # defaulter: first unpaid installment / cycle
    postings: list[tuple[int, str, int, int]] = field(default_factory=list)  # (day, role, debit, credit)
    status: list[tuple[int, str]] = field(default_factory=list)
    schedule: list[dict] = field(default_factory=list)
    line_versions: list[tuple] = field(default_factory=list)  # (day, line, paid, unpaid, paid_day)
    cycles: list[dict] = field(default_factory=list)
    cycle_versions: list[tuple] = field(default_factory=list)  # (day, cycle, paid, overdue_start, last_pay)
    dpd_marks: list[tuple[int, int | None]] = field(default_factory=list)  # (day, oldest unpaid due or None)
    repayments: list[tuple[int, int]] = field(default_factory=list)  # (day, amount)
    draws: list[tuple[int, int]] = field(default_factory=list)


def _next_month_end(n: int) -> int:
    d = to_date(n)
    first_next = d.replace(year=d.year + (d.month == 12), month=d.month % 12 + 1, day=1)
    return day(first_next) - 1


class Book:
    """Balances, overdue slices and postings of one contract."""

    def __init__(self, c: Contract) -> None:
        self.c = c
        self.bal = dict.fromkeys(ROLES, 0)
        self.slices: dict[str, list[list]] = {"principal": [], "interest": []}  # [due, remaining, line]
        self.pen_from: int | None = None
        self.oldest: int | None = None
        self.cursor = c.open_day
        self.dead = False

    def post(self, d: int, role: str, debit: int = 0, credit: int = 0) -> None:
        if debit or credit:
            self.c.postings.append((d, role, debit, credit))
            self.bal[role] += debit - credit

    def mark(self, d: int) -> None:
        dues = [s[0] for k in self.slices.values() for s in k]
        oldest = min(dues) if dues else None
        if oldest != self.oldest:
            self.oldest = oldest
            self.c.dpd_marks.append((d, oldest))

    def advance(self, d: int) -> bool:
        """Month-end penalties and the write-off check up to day d. False once written off."""
        if self.dead:
            return False
        while True:
            me = _next_month_end(self.cursor + 1) if self.cursor < d else None
            wo = self.oldest + WRITE_OFF_DPD if self.oldest is not None else None
            nxt = min(x for x in (me, wo, d + 1) if x is not None)
            if nxt > d:
                self.cursor = d
                return True
            if nxt == wo:
                self.accrue_penalty(wo)
                self.write_off(wo)
                return False
            self.accrue_penalty(nxt)
            self.cursor = nxt

    def to_overdue(self, d: int, kind: str, amount: int, line: int | None) -> None:
        if amount <= 0:
            return
        src, dst = ("principal", "overdue_principal") if kind == "principal" else ("interest", "overdue_interest")
        self.post(d, dst, debit=amount)
        self.post(d, src, credit=amount)
        self.slices[kind].append([d, amount, line])
        if kind == "principal" and self.pen_from is None:
            self.pen_from = d + 1
        self.mark(d)

    def pay(self, d: int, amount: int, current: list[tuple[str, int]] | None = None) -> tuple[int, int, dict]:
        """Overdue interest → overdue principal (oldest first) → current dues → penalty.

        Returns (paid, principal paid, paid per schedule line / current role)."""
        left, principal_paid, by_line = amount, 0, {}
        for kind, role in (("interest", "overdue_interest"), ("principal", "overdue_principal")):
            for s in self.slices[kind]:
                if left <= 0:
                    break
                x = min(left, s[1])
                s[1] -= x
                left -= x
                self.post(d, role, credit=x)
                if kind == "principal":
                    principal_paid += x
                if s[2] is not None:
                    by_line[s[2]] = by_line.get(s[2], 0) + x
            self.slices[kind] = [s for s in self.slices[kind] if s[1] > 0]
        for role, cap in current or []:
            x = min(left, cap, self.bal[role])
            if x > 0:
                left -= x
                self.post(d, role, credit=x)
                by_line[(role,)] = x
                if role == "principal":
                    principal_paid += x
        x = min(left, self.bal["penalty"])
        if x > 0:
            left -= x
            self.post(d, "penalty", credit=x)
        if not self.slices["principal"]:
            self.pen_from = None
        self.mark(d)
        paid = amount - left
        if paid:
            self.c.repayments.append((d, paid))
        return paid, principal_paid, by_line

    def accrue_penalty(self, d: int) -> None:
        if self.pen_from is not None and self.bal["overdue_principal"] > 0 and d >= self.pen_from:
            self.post(d, "penalty", debit=round(self.bal["overdue_principal"] * PENALTY_DAILY * (d - self.pen_from + 1)))
            self.pen_from = d + 1

    def overdue_total(self) -> int:
        return self.bal["overdue_principal"] + self.bal["overdue_interest"] + self.bal["penalty"]

    def write_off(self, d: int) -> None:
        p = self.bal["principal"] + self.bal["overdue_principal"]
        i = self.bal["interest"] + self.bal["overdue_interest"]
        for role in ("principal", "overdue_principal", "interest", "overdue_interest", "penalty", "limit"):
            self.post(d, role, credit=self.bal[role])
        self.post(d, "write_off", debit=p)
        self.post(d, "write_off_interest", debit=i)
        self.slices = {"principal": [], "interest": []}
        self.pen_from = None
        self.mark(d)
        self.c.status.append((d, "written_off"))
        self.dead = True

    def settled(self) -> bool:
        return all(self.bal[r] == 0 for r in ("principal", "interest", "overdue_principal", "overdue_interest", "penalty"))


def run_microloan(c: Contract, rng: np.random.Generator, end: int) -> None:
    b, r, n, P = Book(c), c.rate / 12, c.term, c.amount
    c.status.append((c.open_day, "active"))
    b.post(c.open_day, "principal", debit=P)
    annuity = round(P * r / (1 - (1 + r) ** -n))
    rest = P
    for k in range(n):
        due = add_months(c.open_day, k + 1)
        interest = round(rest * r)
        principal = rest if k == n - 1 else annuity - interest
        rest -= principal
        for kind, amt in (("principal", principal), ("interest", interest)):
            c.schedule.append({"line": len(c.schedule), "k": k, "kind": kind, "due": due, "amount": amt, "paid": 0,
                               "paid_day": None})
            c.line_versions.append((c.open_day, len(c.schedule) - 1, 0, 0, None))

    plan: dict[int, list] = {}
    partial_done = False
    for k in range(n):
        due = c.schedule[2 * k]["due"]
        if c.behaviour == "defaulter" and k >= c.stop:
            if not partial_done and rng.random() < 0.4:
                plan.setdefault(due + int(rng.integers(15, 200)), []).append(("partial", float(rng.uniform(0.2, 0.6))))
                partial_done = True
            continue
        late = c.behaviour in ("late", "defaulter") and rng.random() < 0.35
        delay = int(min(1 + rng.geometric(0.08), 120)) if late else 0
        plan.setdefault(due + delay, []).append(("all", k) if late else ("due", k))

    def record(d: int, lines: dict) -> None:
        for key, x in lines.items():
            ln = c.schedule[key]
            ln["paid"] += x
            ln["paid_day"] = d
            c.line_versions.append((d, key, ln["paid"], max(0, ln["amount"] - ln["paid"]) if ln["due"] <= d else 0, d))

    last_due = c.schedule[-1]["due"]
    for d in sorted({ln["due"] for ln in c.schedule} | set(plan)):
        if d > end:
            break
        if not b.advance(d):
            return
        dues = [ln for ln in c.schedule if ln["due"] == d]
        for ln in dues:
            if ln["kind"] == "interest":
                b.post(d, "interest", debit=ln["amount"])
        for what, arg in plan.get(d, []):
            if what == "due":
                pl_, il_ = c.schedule[2 * arg], c.schedule[2 * arg + 1]
                _, _, lines = b.pay(d, pl_["amount"] + il_["amount"],
                                    [("interest", il_["amount"]), ("principal", pl_["amount"])])
                lines = {(il_ if k_ == ("interest",) else pl_)["line"] if isinstance(k_, tuple) else k_: v
                         for k_, v in lines.items()}
            else:
                b.accrue_penalty(d)
                amount = b.overdue_total() if what == "all" else round(b.overdue_total() * arg)
                _, _, lines = b.pay(d, amount)
            record(d, lines)
        for ln in dues:
            unpaid = ln["amount"] - ln["paid"]
            if unpaid > 0:
                b.to_overdue(d, ln["kind"], unpaid, ln["line"])
                c.line_versions.append((d, ln["line"], ln["paid"], unpaid, ln["paid_day"]))
        if d >= last_due and b.settled():
            c.status.append((d, "closed"))
            return
    b.advance(end)


def run_credit_line(c: Contract, rng: np.random.Generator, end: int) -> None:
    """Monthly statements on the opening day of month; 20-day grace to the due date; minimum payment
    10% of principal (floor 100,000 UZS) plus interest and overdue; interest only after a cycle not
    repaid in full. Each cycle window's events (purchases, the previous statement's payment, its due
    date, a late payment before the next statement) run in day order."""
    b, L = Book(c), c.amount
    c.status.append((c.open_day, "active"))
    b.post(c.open_day, "limit", debit=L)
    blocked, prev_full, cycle_start, k, pending = False, True, c.open_day, 0, None
    dormant_after = int(rng.integers(0, 3)) if c.behaviour == "dormant" else 10**6
    while True:
        statement = add_months(c.open_day, k + 1)
        events: list[tuple[int, int, str, int]] = []
        if not blocked and k < dormant_after:
            n_draws = int(rng.integers(2, 8))
            when = rng.integers(cycle_start, statement, size=n_draws).tolist()
            parts = (rng.dirichlet(np.ones(n_draws)) * L * c.utilisation * rng.uniform(0.5, 1.2)).tolist()
            events += [(d, 1, "draw", int(x)) for d, x in zip(when, parts, strict=True)]
        if pending:
            if pending["pay_day"] is not None:
                pay_day = min(pending["pay_day"], statement - 1)
                events.append((pay_day, 0 if pay_day <= pending["due"] else 3, "pay", pending["pay_amt"]))
            events.append((pending["due"], 2, "due", 0))
        for d, _, what, x in sorted(events):
            if d > end:
                b.advance(end)
                return
            if not b.advance(d):
                return
            if what == "draw":
                x = min(x, b.bal["limit"]) // 100_00 * 100_00
                if x > 0 and not blocked:
                    b.post(d, "principal", debit=x)
                    b.post(d, "limit", credit=x)
                    c.draws.append((d, x))
            elif what == "pay":
                y = pending
                late = d > y["due"]
                if late:
                    b.accrue_penalty(d)
                current = None if late else [("interest", y["interest_due"]), ("principal", y["principal"])]
                got, principal_got, _ = b.pay(d, x, current)
                if principal_got:
                    b.post(d, "limit", debit=principal_got)
                y["paid"] += got
                y["paid_principal"] += principal_got
                c.cycle_versions.append((d, y["ci"], y["paid"], y["overdue_start"], d))
            else:
                y = pending
                short_p = min(max(0, y["min_principal"] - y["paid_principal"]), b.bal["principal"])
                short_i = b.bal["interest"]
                if short_p or short_i:
                    b.to_overdue(d, "principal", short_p, None)
                    b.to_overdue(d, "interest", short_i, None)
                    y["overdue_start"] = d
                    c.cycle_versions.append((d, y["ci"], y["paid"], d, None))
                dpd = (d - b.oldest) if b.oldest is not None else 0
                if dpd > 30 and not blocked:
                    blocked = True
                    c.status.append((d, "blocked"))
                elif blocked and b.oldest is None:
                    blocked = False
                    c.status.append((d, "active"))
        if pending:
            prev_full = pending["paid"] >= pending["balance"]
        if statement > end:
            b.advance(end)
            return
        if not b.advance(statement):
            return
        principal = b.bal["principal"]
        if principal > 0 and not prev_full:
            b.post(statement, "interest", debit=round(principal * c.rate * 30 / 365))
        interest_due = b.bal["interest"]
        min_principal = min(principal, max(round(principal * 0.1), MIN_PAY_FLOOR))
        balance = principal + interest_due + b.overdue_total()
        min_pay = min_principal + interest_due + b.overdue_total()
        due = statement + 20
        c.cycles.append({"statement": statement, "start": cycle_start, "due": due, "balance": balance, "min": min_pay,
                         "used": principal})
        ci = len(c.cycles) - 1
        c.cycle_versions.append((statement, ci, 0, None, None))
        pay_day, pay_amt = None, 0
        if balance > 0:
            if c.behaviour == "defaulter" and k >= c.stop:
                if rng.random() < 0.1:
                    pay_day, pay_amt = due + int(rng.integers(1, 10)), round(min_pay * rng.uniform(0.2, 0.7))
            elif c.behaviour in ("late", "defaulter") and rng.random() < 0.35:
                pay_day, pay_amt = due + int(rng.integers(1, 10)), min_pay
            elif c.transactor or c.behaviour == "dormant":
                pay_day, pay_amt = statement + int(rng.integers(3, 20)), balance
            else:
                pay_day, pay_amt = statement + int(rng.integers(5, 20)), int(rng.uniform(min_pay, max(min_pay, 0.6 * balance)))
        pending = {"ci": ci, "due": due, "pay_day": pay_day, "pay_amt": pay_amt, "interest_due": interest_due,
                   "principal": principal, "min_principal": min_principal, "balance": balance, "paid": 0,
                   "paid_principal": 0, "overdue_start": None}
        cycle_start, k = statement + 1, k + 1


def states(c: Contract, end: int) -> list[tuple[int, str, int]]:
    """Delinquency state changes (day, state, days past due) from the oldest-unpaid timeline."""
    out: list[tuple[int, str, int]] = []
    current = "current"
    written = {d for d, s in c.status if s == "written_off"}

    def bucket(dpd: int) -> str:
        name = "current"
        for threshold, label in STATES:
            if dpd >= threshold:
                name = label
        return name

    marks = c.dpd_marks + [(end + 1, None)]
    for (d, oldest), (nxt, _) in pairwise(marks):
        if d in written:
            out.append((d, "written_off", 0))
            return out
        if oldest is None:
            if current != "current":
                out.append((d, "current", 0))
                current = "current"
            continue
        dpd0 = d - oldest
        if bucket(dpd0) != current:
            current = bucket(dpd0)
            out.append((d, current, dpd0))
        for threshold, name in STATES:
            t = oldest + threshold
            if d < t < nxt and t <= end and threshold > dpd0:
                out.append((t, name, threshold))
                current = name
    return out
