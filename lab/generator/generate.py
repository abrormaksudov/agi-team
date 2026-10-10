"""Generate the fictional bank's source data: lab/data/<source>/<oper_day>/<schema>.<table>.csv.

    uv run --group generator python lab/generator/generate.py --scale 10000

Seeded and reproducible. Day 0 (the snapshot) carries all history; each later day carries that day's
new and changed rows. See docs/story.md.
"""

import argparse
import shutil
import time
from datetime import date
from pathlib import Path

import numpy as np
import polars as pl
from bank import core, daily, mobile, people, ref, tx
from bank.checks import check
from bank.util import day
from bank.write import Sink

HISTORY_START = date(2024, 9, 1)
SNAPSHOT = date(2026, 7, 31)
END = date(2026, 9, 30)
OUT = Path(__file__).resolve().parents[1] / "data"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scale", type=int, default=10_000, help="persons (app users before duplicates)")
    parser.add_argument("--seed", type=int, default=20261010)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()

    started = time.time()
    rng = np.random.default_rng(args.seed)
    start, snapshot, end = day(HISTORY_START), day(SNAPSHOT), day(END)
    r = ref.load()

    def step(name: str) -> None:
        print(f"[{time.time() - started:6.1f}s] {name}", flush=True)

    folk = people.make(rng, r, args.scale, start, end)
    step(f"people: {folk.n}")
    users = mobile.make_users(rng, folk, end)
    kyc = mobile.make_kyc(rng, folk, users, end)
    kyc_day = np.full(folk.n, -1)
    first = users.kyc_day[: folk.n]
    kyc_day[first >= 0] = first[first >= 0]
    step(f"mobile: {len(users.person)} app users, {kyc.height} KYC attempts")

    bank, iabs_tables = core.make(rng, r, folk, kyc_day, start, snapshot, end, core.exchange_rates(rng, r, start, end))
    iabs_tables |= core.dictionaries(r, start, end, snapshot)
    iabs_tables["account"] = (core.accounts_frame(bank.accounts, end), ["account_id"])
    step(f"iabs: {int((bank.customer_id >= 0).sum())} customers, {len(bank.accounts.account_id)} accounts")

    engine = tx.make(rng, r, folk, bank, snapshot, end)
    step(f"tranzaxis: {len(engine.contracts)} credit contracts, {engine.cards.height} cards")

    sim = daily.run(rng, r, folk, bank, engine, snapshot, end)
    iabs_tables["account_balance"] = sim.pop("account_balance")
    iabs_tables["payment_document"] = sim.pop("payment_document")
    engine.tables["card_transaction"] = sim.pop("card_transaction")
    step("daily simulation")

    device, user_device = mobile.devices_frames(rng, users, end)
    logins = mobile.logins_frame(rng, folk, users, range(snapshot + 1, end + 1), 1)
    app_users = mobile.users_frame(folk, users, bank.customer_id, rng)

    sink = Sink()
    sink.add("mobile", "users", "app_user", app_users, ["user_id"])
    sink.add("mobile", "users", "login_event", logins, ["event_id"])
    sink.add("mobile", "devices", "device", device, ["device_id"])
    sink.add("mobile", "devices", "user_device", user_device, ["user_device_id"])
    sink.add("mobile", "kyc", "kyc_attempt", kyc, ["attempt_id"])
    for name, (frame, key) in iabs_tables.items():
        sink.add("iabs", "core", name, frame, key)
    for name, (frame, key) in engine.tables.items():
        sink.add("tranzaxis", "tx", name, frame, key)

    check(sink, snapshot, end)
    step("invariants hold")
    if args.out.exists():
        for source in ("iabs", "mobile", "tranzaxis"):
            shutil.rmtree(args.out / source, ignore_errors=True)
    counts = sink.write(args.out, snapshot, end)
    step(f"written to {args.out}")
    with pl.Config(tbl_rows=60):
        print(pl.DataFrame({"table": list(counts), "rows": list(counts.values())}))


if __name__ == "__main__":
    main()
