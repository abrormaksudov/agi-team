"""Versioned rows → one folder per operating day, one CSV per source table.

Every frame carries `_v`, the day the row version takes effect. Day 0 (the snapshot) gets each key's
latest version up to the snapshot; each later day gets that day's versions. The loader upserts by
primary key, so a later version of a contract or schedule line replaces the earlier one.
"""

from collections import defaultdict
from pathlib import Path

import polars as pl

from .util import to_date


class Sink:
    def __init__(self) -> None:
        self.parts: dict[tuple[str, str, str], list[pl.DataFrame]] = defaultdict(list)
        self.keys: dict[tuple[str, str, str], list[str]] = {}

    def add(self, source: str, schema: str, table: str, frame: pl.DataFrame, key: list[str]) -> None:
        if frame.height:
            self.parts[(source, schema, table)].append(frame)
        self.keys[(source, schema, table)] = key

    def frame(self, source: str, schema: str, table: str) -> pl.DataFrame:
        return pl.concat(self.parts[(source, schema, table)], how="diagonal_relaxed")

    def write(self, out: Path, snapshot: int, end: int) -> dict[str, int]:
        counts: dict[str, int] = {}
        for (source, schema, table), key in sorted(self.keys.items()):
            if not self.parts[(source, schema, table)]:
                continue
            frame = self.frame(source, schema, table).sort("_v", maintain_order=True)
            days = [(snapshot, frame.filter(pl.col("_v") <= snapshot))]
            later = frame.filter(pl.col("_v") > snapshot)
            for (v,), part in later.partition_by("_v", as_dict=True).items():
                if v <= end:
                    days.append((v, part))
            total = 0
            for v, part in days:
                part = part.unique(subset=key, keep="last", maintain_order=True).drop("_v")
                if not part.height:
                    continue
                folder = out / source / to_date(v).isoformat()
                folder.mkdir(parents=True, exist_ok=True)
                part.write_csv(folder / f"{schema}.{table}.csv", null_value="")
                total += part.height
            counts[f"{source}.{schema}.{table}"] = total
        return counts
