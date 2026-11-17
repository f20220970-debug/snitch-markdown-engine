"""Load the raw transactions and build the weekly SKU panel every other module uses.

Data: 541,909 real transaction lines from a UK online retailer, Dec 2010 - Dec 2011 (public
"Online Retail" dataset). Real prices that move week to week, and real cancellations, which is what a
markdown study needs. Snitch's own sales data is private, so this is a stand-in: the method transfers,
the numbers will not.

Panel columns per SKU-week: units, realised price, orders, returned units, and the SKU's own base price.
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "online_retail.csv"
MIN_WEEKS, MIN_UNITS = 20, 200          # a SKU needs history before any of this means anything


def load_raw() -> pd.DataFrame:
    d = pd.read_csv(RAW, dtype={"InvoiceNo": str, "StockCode": str, "Description": str, "Country": str},
                    parse_dates=["InvoiceDate"])
    d["is_return"] = d.InvoiceNo.str.startswith("C")
    return d


def build_panel(d: pd.DataFrame):
    """Returns (panel, sku_info). A 'C' invoice is a cancellation, so those lines are the returns."""
    d = d[d.UnitPrice > 0].copy()
    d["wk"] = d.InvoiceDate.dt.to_period("W").dt.start_time
    sales = d[~d.is_return & (d.Quantity > 0)]
    rets = d[d.is_return]

    g = sales.groupby(["StockCode", "wk"])
    panel = pd.DataFrame({
        "units": g.Quantity.sum(),
        "revenue": g.apply(lambda x: float((x.Quantity * x.UnitPrice).sum()), include_groups=False),
        "orders": g.InvoiceNo.nunique(),
    }).reset_index()
    panel["price"] = panel.revenue / panel.units

    r = rets.groupby(["StockCode", "wk"]).Quantity.sum().abs().rename("returned_units")
    panel = panel.merge(r, on=["StockCode", "wk"], how="left")
    panel["returned_units"] = panel.returned_units.fillna(0)

    info = panel.groupby("StockCode").agg(weeks=("wk", "size"), units=("units", "sum"),
                                          returned=("returned_units", "sum"), revenue=("revenue", "sum"))
    # base price = the 75th percentile of realised weekly price: what the SKU sells at when it is NOT discounted
    info["base_price"] = panel.groupby("StockCode").price.quantile(0.75)
    info["return_rate"] = info.returned / info.units.clip(lower=1)
    info["desc"] = sales.groupby("StockCode").Description.agg(lambda s: s.mode().iloc[0] if len(s.mode()) else "")
    keep = info[(info.weeks >= MIN_WEEKS) & (info.units >= MIN_UNITS)].copy()

    panel = panel[panel.StockCode.isin(keep.index)].merge(keep[["base_price"]], on="StockCode")
    panel["discount"] = (1 - panel.price / panel.base_price).clip(lower=0, upper=0.9)
    panel["week_index"] = panel.wk.rank(method="dense").astype(int)
    return panel.sort_values(["StockCode", "wk"]).reset_index(drop=True), keep


def seasonality(panel: pd.DataFrame) -> pd.Series:
    """Store-wide demand index per week: total units that week / median week. Controls for Christmas etc.,
    so a price effect is not confused with a December rush."""
    tot = panel.groupby("wk").units.sum()
    return (tot / tot.median()).rename("season")


def load() -> tuple:
    d = load_raw()
    panel, info = build_panel(d)
    panel = panel.merge(seasonality(panel), on="wk")
    return panel, info
