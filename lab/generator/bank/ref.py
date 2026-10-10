"""Reference dictionaries from lab/generator/reference/."""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import polars as pl

REFERENCE = Path(__file__).resolve().parent.parent / "reference"


def _read(name: str) -> pl.DataFrame:
    return pl.read_csv(REFERENCE / f"{name}.csv", infer_schema_length=0)


def _weights(column: pl.Series) -> np.ndarray:
    w = column.cast(pl.Float64).to_numpy()
    return w / w.sum()


@dataclass
class Reference:
    first_names: pl.DataFrame
    surnames: pl.DataFrame
    regions: pl.DataFrame
    districts: pl.DataFrame
    phone_prefixes: pl.DataFrame
    mcc: pl.DataFrame
    currencies: pl.DataFrame
    holidays: pl.DataFrame
    balance_accounts: pl.DataFrame

    def weights(self, frame: str, column: str = "weight") -> np.ndarray:
        return _weights(getattr(self, frame)[column])

    def balance_account(self, section: str, product_hint: str, fx: bool = False) -> str:
        """First chart code of a section and product; FX variants are the next code in the chart.
        Memorandum (off-balance) sections prefer off-balance codes."""
        rows = self.balance_accounts.filter((pl.col("section") == section) & (pl.col("product_hint") == product_hint))
        if section in ("written_off", "commitments", "collateral"):
            rows = rows.filter(pl.col("class") == "off_balance")
        codes = rows["code"].to_list()
        if not codes:
            raise KeyError(f"no balance account for {section}/{product_hint}")
        return codes[1] if fx and len(codes) > 1 else codes[0]


def load() -> Reference:
    return Reference(
        first_names=_read("first_names"),
        surnames=_read("surnames"),
        regions=_read("regions"),
        districts=_read("districts"),
        phone_prefixes=_read("phone_prefixes"),
        mcc=_read("mcc"),
        currencies=_read("currencies"),
        holidays=_read("holidays"),
        balance_accounts=_read("balance_accounts"),
    )
