"""mobile: app users, devices, KYC attempts, login events (in-house mobile banking backend)."""

from dataclasses import dataclass

import numpy as np
import polars as pl

from .people import People
from .util import daytime_seconds, hexes, to_date, ts, uuids

STEPS = ["personal_data", "document_scan", "liveness", "address", "product_selection"]
FAIL_REASONS = {
    "document_expired": "document_scan",
    "document_unreadable": "document_scan",
    "liveness_failed": "liveness",
    "face_mismatch": "liveness",
    "nibbd_check_failed": "personal_data",
    "session_timeout": "address",
}
ANDROID = ["Samsung Galaxy A54", "Samsung Galaxy A34", "Xiaomi Redmi Note 13", "Xiaomi Redmi 13C", "Samsung Galaxy S23",
           "Tecno Spark 20", "Honor X8b", "Vivo Y36", "Infinix Hot 40", "Xiaomi Poco X6"]
IOS = ["iPhone 11", "iPhone 12", "iPhone 13", "iPhone 14", "iPhone 15", "iPhone 15 Pro", "iPhone 16"]
RELEASES = [("2024-09-01", "3.7.0"), ("2025-01-15", "3.8.0"), ("2025-04-10", "3.9.0"), ("2025-07-01", "4.0.0"),
            ("2025-10-05", "4.1.0"), ("2026-01-20", "4.2.0"), ("2026-04-14", "4.3.0"), ("2026-07-08", "4.4.0"),
            ("2026-09-02", "4.5.0")]


def app_version(n: int) -> str:
    d = to_date(n).isoformat()
    return next(v for released, v in reversed(RELEASES) if released <= d)


@dataclass
class AppUsers:
    person: np.ndarray  # app user index → person index
    user_id: list[str]
    registered: np.ndarray
    registered_sec: np.ndarray
    kyc_day: np.ndarray  # day of successful onboarding KYC, -1 if never
    devices: dict[int, list[str]]  # app user index → device ids


def make_users(rng: np.random.Generator, people: People, end: int) -> AppUsers:
    """App accounts: one per person, plus ~2% duplicates (same PINFL, second phone) registered later."""
    dup_from = np.flatnonzero(rng.random(people.n) < 0.02)
    dup_reg = people.registered[dup_from] + rng.integers(30, 400, size=len(dup_from))
    keep = dup_reg <= end
    dup_from, dup_reg = dup_from[keep], dup_reg[keep]
    person = np.concatenate([np.arange(people.n), dup_from])
    registered = np.concatenate([people.registered, dup_reg])
    registered_sec = np.concatenate([people.registered_sec, rng.integers(7 * 3600, 23 * 3600, size=len(dup_from))])
    return AppUsers(person=person, user_id=uuids(rng, len(person)), registered=registered,
                    registered_sec=registered_sec, kyc_day=np.full(len(person), -1), devices={})


def make_kyc(rng: np.random.Generator, people: People, users: AppUsers, end: int) -> pl.DataFrame:
    """Onboarding attempts (1–3, ~80% of persons pass; duplicates pass and link to the same person),
    plus later re-verifications for new devices and password resets."""
    n = len(users.person)
    passes = rng.random(people.n) < 0.80
    rows: list[tuple] = []
    attempt_ids = iter(uuids(rng, n * 4))
    r_attempts, r_delay, r_reason, r_score, r_hold = (rng.random(n), rng.integers(1, 72 * 3600, size=n * 3),
                                                      rng.integers(0, len(FAIL_REASONS), size=n * 3),
                                                      rng.random(n * 3), rng.random(n))
    reasons = list(FAIL_REASONS)
    for u in range(n):
        p = users.person[u]
        dup = u >= people.n
        ok = passes[p]
        k = 1 if dup else (1 if r_attempts[u] < 0.70 else 2 if r_attempts[u] < 0.92 else 3)
        t_day, t_sec = int(users.registered[u]), int(users.registered_sec[u]) + 120
        for a in range(k):
            last = a == k - 1
            started = (t_day, t_sec)
            reason = None
            if last and ok:
                status, step, score = "SUCCESS", STEPS[-1], 0.75 + 0.24 * r_score[u * 3 + a]
                aml = "GREEN"
            else:
                reason = reasons[r_reason[u * 3 + a]]
                status = "REFUSE" if (last and r_score[u * 3 + a] < 0.3) else "FAIL"
                step = FAIL_REASONS[reason]
                score = 0.2 + 0.49 * r_score[u * 3 + a] if reason == "face_mismatch" else 0.75 + 0.2 * r_score[u * 3 + a]
                aml = "RED" if status == "REFUSE" and reason == "nibbd_check_failed" else "GREEN"
            hold = status == "SUCCESS" and r_hold[u] < 0.05
            dur = 300 + (r_delay[u * 3 + a] % 900)
            done_day, done_sec = t_day, t_sec + dur
            if hold:
                done_day += 1 + int(r_hold[u] * 40)
            if done_sec >= 86400:
                done_day, done_sec = done_day + 1, done_sec - 86400
            if done_day > end:
                break
            aid = next(attempt_ids)
            base = (aid, users.user_id[u], "onboarding", "first", step, reason, round(float(score), 3),
                    f"kyc-photos/{to_date(started[0]):%Y/%m}/{aid}.jpg", aml, None)
            if hold:
                rows.append((*base[:4], "HOLD", "liveness", None, *base[6:9], ts(*started), None, ts(*started), started[0]))
            rows.append((*base[:4], status, *base[4:9], ts(*started), ts(done_day, done_sec), ts(done_day, done_sec),
                         done_day))
            if status == "SUCCESS":
                users.kyc_day[u] = done_day
            t_day, t_sec = done_day, done_sec + int(r_delay[u * 3 + a] % 7200)
            if t_sec >= 86400:
                t_day, t_sec = t_day + 1, t_sec - 86400
    # Re-verifications after onboarding: new device (15%), password reset (8%).
    for purpose, share in (("new_device_login", 0.15), ("password_reset", 0.08)):
        who = np.flatnonzero((users.kyc_day >= 0) & (rng.random(n) < share))
        when = users.kyc_day[who] + rng.integers(10, 500, size=len(who))
        sec = daytime_seconds(rng, len(who))
        good = rng.random(len(who)) < 0.95
        for u, d, s, g in zip(who, when, sec, good, strict=True):
            if d > end:
                continue
            aid = next(attempt_ids)
            status, step, reason = ("SUCCESS", "liveness", None) if g else ("FAIL", "liveness", "liveness_failed")
            done = min(int(s) + 240, 86399)
            rows.append((aid, users.user_id[u], purpose, "re_verification", status, step, reason,
                         round(float(0.8 + 0.19 * rng.random()) if g else 0.4, 3),
                         f"kyc-photos/{to_date(d):%Y/%m}/{aid}.jpg", "GREEN", ts(d, s), ts(d, done), ts(d, done), int(d)))
    cols = ["attempt_id", "user_id", "purpose", "mode", "status", "last_step", "fail_reason", "face_match_score",
            "face_photo_ref", "aml_result", "started_at", "completed_at", "updated_at", "_v"]
    frame = pl.DataFrame(rows, schema=cols, orient="row", infer_schema_length=None)
    return frame.with_columns(pl.col("_v").cast(pl.Int32))


def users_frame(people: People, users: AppUsers, customer_id: np.ndarray, rng: np.random.Generator) -> pl.DataFrame:
    """app_user versions: on registration (unverified), on successful KYC (verified, linked to core customer)."""
    p = users.person
    with_email = rng.random(len(p)) < 0.35
    domains = rng.choice(["gmail.com", "mail.ru", "yandex.ru", "inbox.uz", "icloud.com"], size=len(p))
    clean = np.vectorize(lambda s: s.lower().replace("'", ""))
    email = np.where(with_email, np.char.add(np.char.add(np.char.add(clean(people.first_name[p]), "."),
                                                         clean(people.last_name[p])), np.char.add("@", domains)), None)
    phone = people.phone[p].copy()
    dup = np.arange(len(p)) >= people.n
    phone[dup] = [f"+99833{x:07d}" for x in rng.choice(10_000_000, size=int(dup.sum()), replace=False)]
    status = np.where(rng.random(len(p)) < 0.012, "blocked", "active")
    lang = rng.choice(["uz", "ru", "en"], size=len(p), p=[0.62, 0.34, 0.04])
    base = pl.DataFrame({
        "user_id": users.user_id,
        "phone_number": phone,
        "email": pl.Series(email.tolist(), dtype=pl.Utf8),
        "first_name": people.first_name[p],
        "last_name": people.last_name[p],
        "middle_name": people.middle_name[p],
        "date_of_birth": [to_date(b) for b in people.birth[p]],
        "gender": people.gender[p],
        "pinfl": people.pinfl[p],
        "lang": lang,
        "account_status": "active",
        "verification_level": "none",
        "core_customer_id": pl.Series([None] * len(p), dtype=pl.Int64),
        "created_at": [ts(d, s) for d, s in zip(users.registered, users.registered_sec, strict=True)],
        "_v": users.registered.astype(np.int32),
    })
    base = base.with_columns(pl.col("created_at").alias("updated_at"))
    verified = (users.kyc_day >= 0) & (customer_id[p] >= 0)
    v2 = base.filter(pl.Series(verified)).with_columns(
        pl.lit("full").alias("verification_level"),
        pl.Series(customer_id[p[verified]]).alias("core_customer_id"),
        pl.Series(status[verified]).alias("account_status"),
        pl.Series([ts(d, 43200) for d in users.kyc_day[verified]]).alias("updated_at"),
        pl.Series(users.kyc_day[verified].astype(np.int32)).alias("_v"),
    )
    return pl.concat([base, v2])


def devices_frames(rng: np.random.Generator, users: AppUsers, end: int) -> tuple[pl.DataFrame, pl.DataFrame]:
    n = len(users.person)
    count = 1 + np.minimum(rng.poisson(0.35, size=n), 3)
    owner = np.repeat(np.arange(n), count)
    first = np.r_[True, owner[1:] != owner[:-1]]
    seen = np.where(first, users.registered[owner], users.registered[owner] + rng.integers(20, 600, size=len(owner)))
    keep = seen <= end
    owner, seen, first = owner[keep], seen[keep], first[keep]
    m = len(owner)
    android = rng.random(m) < 0.76
    ids = uuids(rng, m)
    for i, u in enumerate(owner):
        users.devices.setdefault(int(u), []).append(ids[i])
    sec = daytime_seconds(rng, m)
    device = pl.DataFrame({
        "device_id": ids,
        "device_fingerprint": hexes(rng, m),
        "platform": np.where(android, "android", "ios"),
        "device_model": np.where(android, rng.choice(ANDROID, m), rng.choice(IOS, m)),
        "os_version": np.where(android, np.char.add("Android ", rng.integers(11, 16, m).astype(str)),
                               np.char.add("iOS ", rng.integers(16, 19, m).astype(str))),
        "app_version": [app_version(d) for d in seen],
        "first_seen_at": [ts(d, s) for d, s in zip(seen, sec, strict=True)],
        "_v": seen.astype(np.int32),
    })
    rooted = android & (rng.random(m) < 0.015)
    user_device = pl.DataFrame({
        "user_device_id": np.arange(1, m + 1),
        "user_id": [users.user_id[u] for u in owner],
        "device_id": ids,
        "is_trusted": first | (rng.random(m) < 0.6),
        "is_blocked": rng.random(m) < 0.01,
        "is_rooted": rooted,
        "malware_detected": rng.random(m) < 0.005,
        "malware_scan_at": [ts(d, s) for d, s in zip(seen, sec + 60, strict=True)],
        "first_linked_at": [ts(d, s) for d, s in zip(seen, sec, strict=True)],
        "_v": seen.astype(np.int32),
    })
    return device, user_device


def logins_frame(rng: np.random.Generator, people: People, users: AppUsers, days: range, start_id: int) -> pl.DataFrame:
    """Login events for the simulated days: ~activity share of users per day, plus register events."""
    frames, next_id = [], start_id
    activity = people.activity[users.person]
    first_device = np.array([users.devices.get(u, [None])[0] for u in range(len(users.person))], dtype=object)
    user_ids = np.array(users.user_id, dtype=object)
    for d in days:
        weekend = to_date(d).weekday() >= 5
        eligible = users.registered < d
        active = eligible & (rng.random(len(activity)) < activity * (0.34 if weekend else 0.4))
        idx = np.flatnonzero(active)
        reps = 1 + rng.poisson(0.5, size=len(idx))
        who = np.repeat(idx, reps)
        new = np.flatnonzero(users.registered == d)
        who = np.concatenate([who, new])
        kind = np.where(np.arange(len(who)) >= len(who) - len(new), "register",
                        np.where(rng.random(len(who)) < 0.18, "logout", "login"))
        result = np.where(kind == "register", "success",
                          rng.choice(["success", "wrong_password", "otp_timeout"], size=len(who), p=[0.96, 0.03, 0.01]))
        sec = daytime_seconds(rng, len(who))
        ip = rng.integers(0, 2**22, size=len(who))
        version = app_version(d)
        frames.append(pl.DataFrame({
            "event_id": np.arange(next_id, next_id + len(who)),
            "user_id": pl.Series(user_ids[who].tolist(), dtype=pl.Utf8),
            "device_id": pl.Series(first_device[who].tolist(), dtype=pl.Utf8),
            "session_id": uuids(rng, len(who)),
            "event_type": kind,
            "auth_result": result,
            "ip_address": [f"100.{64 + (x >> 16)}.{(x >> 8) & 255}.{x & 255}" for x in ip],
            "app_version": version,
            "occurred_at": [ts(d, s) for s in sec],
            "_v": np.full(len(who), d, dtype=np.int32),
        }))
        next_id += len(who)
    return pl.concat(frames)
