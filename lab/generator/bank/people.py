"""Persons: one profile per real person, the root every table derives from."""

from dataclasses import dataclass

import numpy as np

from .ref import Reference
from .util import to_date

BEHAVIOURS = np.array(["good", "late", "defaulter", "dormant"])
BEHAVIOUR_P = [0.68, 0.17, 0.07, 0.08]


@dataclass
class People:
    n: int
    gender: np.ndarray  # "M" / "F"
    birth: np.ndarray  # day
    region: np.ndarray  # region_code
    district: np.ndarray  # district_code
    first_name: np.ndarray
    last_name: np.ndarray
    middle_name: np.ndarray
    pinfl: np.ndarray
    phone: np.ndarray
    passport_series: np.ndarray
    passport_number: np.ndarray
    passport_issued: np.ndarray  # day
    income: np.ndarray  # monthly, tiyin
    employed: np.ndarray  # bool
    salary_day: np.ndarray
    behaviour: np.ndarray
    activity: np.ndarray  # 0..1, daily app / card activity
    registered: np.ndarray  # day of app registration
    registered_sec: np.ndarray


def _pinfl(rng: np.random.Generator, gender: np.ndarray, birth: np.ndarray, district: np.ndarray) -> np.ndarray:
    """14 digits: century+gender (1), birth DDMMYY (6), district (3), serial (3), check (1). Synthetic."""
    out = np.empty(len(gender), dtype=object)
    seen: set[str] = set()
    serials = rng.integers(0, 1000, size=len(gender))
    for i, (g, b, dc, s) in enumerate(zip(gender, birth, district, serials, strict=True)):
        d = to_date(b)
        first = (3 if g == "M" else 4) if d.year < 2000 else (5 if g == "M" else 6)
        while True:
            body = f"{first}{d.day:02d}{d.month:02d}{d.year % 100:02d}{str(dc)[-3:]}{s % 1000:03d}"
            check = sum(int(c) * w for c, w in zip(body, [7, 3, 1] * 5, strict=False)) % 10
            value = f"{body}{check}"
            if value not in seen:
                break
            s += 1
        seen.add(value)
        out[i] = value
    return out


def make(rng: np.random.Generator, ref: Reference, n: int, start: int, end: int) -> People:
    gender = np.where(rng.random(n) < 0.5, "M", "F")
    age_days = ((18 + rng.gamma(2.2, 9.0, size=n).clip(0, 57)) * 365.25).astype(int)
    birth = end - age_days - rng.integers(0, 365, size=n)

    regions = ref.regions["region_code"].to_numpy()
    region = rng.choice(regions, size=n, p=ref.weights("regions", "population_weight"))
    districts_by_region = {
        r: ref.districts.filter(ref.districts["region_code"] == r)["district_code"].to_numpy() for r in regions
    }
    district = np.array([rng.choice(districts_by_region[r]) for r in region])

    names, name_gender = ref.first_names["name"].to_numpy(), ref.first_names["gender"].to_numpy()
    name_w = ref.weights("first_names")
    male = np.flatnonzero(name_gender == "M")
    female = np.flatnonzero(name_gender == "F")
    pm, pf = name_w[male] / name_w[male].sum(), name_w[female] / name_w[female].sum()
    is_m = gender == "M"
    first_name = np.where(is_m, names[rng.choice(male, n, p=pm)], names[rng.choice(female, n, p=pf)])
    father = names[rng.choice(male, n, p=pm)]
    middle_name = np.where(is_m, np.char.add(father.astype(str), " o'g'li"), np.char.add(father.astype(str), " qizi"))
    s_idx = rng.choice(len(ref.surnames), n, p=ref.weights("surnames"))
    last_name = np.where(is_m, ref.surnames["male"].to_numpy()[s_idx], ref.surnames["female"].to_numpy()[s_idx])

    prefixes = ref.phone_prefixes["prefix"].to_numpy()
    prefix = rng.choice(prefixes, n, p=ref.weights("phone_prefixes"))
    local = rng.choice(10_000_000, size=n, replace=False)
    phone = np.array([f"+998{p}{x:07d}" for p, x in zip(prefix, local, strict=True)])

    passport_series = rng.choice(["AA", "AB", "AC", "AD", "AE"], size=n, p=[0.3, 0.3, 0.2, 0.15, 0.05])
    passport_number = np.array([f"{x:07d}" for x in rng.choice(10_000_000, size=n, replace=False)])
    passport_issued = np.maximum(birth + 16 * 366, end - rng.integers(30, 10 * 365, size=n))

    income = (np.exp(rng.normal(np.log(4_500_000), 0.6, size=n)).clip(1_200_000, 80_000_000) // 1000 * 1000) * 100
    employed = rng.random(n) < 0.75
    salary_day = rng.choice([5, 10, 15, 25], size=n)
    behaviour = rng.choice(BEHAVIOURS, size=n, p=BEHAVIOUR_P)
    activity = np.where(behaviour == "dormant", 0.15, 1.0) * rng.beta(2.0, 4.0, size=n)

    span = end - start
    registered = start + (span * rng.random(n) ** (1 / 1.35)).astype(int)
    registered_sec = rng.integers(7 * 3600, 23 * 3600, size=n)

    return People(
        n=n,
        gender=gender,
        birth=birth,
        region=region,
        district=district,
        first_name=first_name,
        last_name=last_name,
        middle_name=middle_name,
        pinfl=_pinfl(rng, gender, birth, district),
        phone=phone,
        passport_series=passport_series,
        passport_number=passport_number,
        passport_issued=passport_issued,
        income=income.astype(np.int64),
        employed=employed,
        salary_day=salary_day,
        behaviour=behaviour,
        activity=activity,
        registered=registered,
        registered_sec=registered_sec,
    )

