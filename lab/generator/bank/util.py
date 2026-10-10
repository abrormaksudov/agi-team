"""Shared helpers: days as int (days since 1970-01-01), ids, account numbers."""

from datetime import date, timedelta

import numpy as np

EPOCH = date(1970, 1, 1)


def day(d: date) -> int:
    return (d - EPOCH).days


def to_date(n: int) -> date:
    return EPOCH + timedelta(days=int(n))


def add_months(n: int, months: int, day_cap: int = 28) -> int:
    d = to_date(n)
    y, m = divmod(d.month - 1 + months, 12)
    last = (date(d.year + y + (m == 11), (m + 1) % 12 + 1, 1) - timedelta(days=1)).day
    return day(date(d.year + y, m + 1, min(d.day, day_cap, last)))


def month_end(n: int) -> bool:
    return to_date(n + 1).day == 1


def uuids(rng: np.random.Generator, n: int) -> list[str]:
    raw = rng.integers(0, 256, size=(n, 16), dtype=np.uint8)
    raw[:, 6] = (raw[:, 6] & 0x0F) | 0x40
    raw[:, 8] = (raw[:, 8] & 0x3F) | 0x80
    out = []
    for b in raw:
        h = b.tobytes().hex()
        out.append(f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:]}")
    return out


def hexes(rng: np.random.Generator, n: int, length: int = 32) -> list[str]:
    raw = rng.integers(0, 256, size=(n, length // 2), dtype=np.uint8)
    return [b.tobytes().hex() for b in raw]


def digits(rng: np.random.Generator, n: int, width: int) -> np.ndarray:
    return np.char.zfill(rng.integers(0, 10**width, size=n).astype(str), width)


def account_number(balance_account: str, currency_numeric: str, customer_code: str, seq: int) -> str:
    """20 digits: balance account (5) + currency (3, 000 for UZS) + check (1) + customer code (8) + sequence (3)."""
    ccy = "000" if currency_numeric == "860" else currency_numeric
    body = f"{balance_account}{ccy}{customer_code}{seq:03d}"
    check = sum(int(c) * w for c, w in zip(body, [7, 1, 3] * 6, strict=False)) % 10
    return f"{balance_account}{ccy}{check}{customer_code}{seq:03d}"


def ts(n: int, seconds: int) -> str:
    """Local Tashkent timestamp of day n plus seconds since midnight (overflow rolls into later days)."""
    n, seconds = n + int(seconds) // 86400, int(seconds) % 86400
    h, rem = divmod(seconds, 3600)
    return f"{to_date(n).isoformat()} {h:02d}:{rem // 60:02d}:{rem % 60:02d}+05"


def daytime_seconds(rng: np.random.Generator, n: int) -> np.ndarray:
    """Seconds since midnight, peaking around noon and evening."""
    hours = np.clip(rng.normal(14.5, 4.2, size=n), 0, 23.999)
    return (hours * 3600).astype(int)
