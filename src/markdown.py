"""Which products to mark down, and by how much, to protect gross profit.

The decision: a SKU has `stock` units left and `weeks` of selling season left. Pick a discount now.
Too little and the stock is left over at the end; too much and margin is given away on units that would
have sold anyway.

    weekly demand at discount x  =  base demand * (1 - x) ** elasticity
    units sold                   =  min(stock, weeks * demand)
    gross profit                 =  units * (price * (1 - x) - cost) + leftover * (salvage - cost)

ASSUMPTIONS, not data (this dataset has no cost or stock figures). Both are inputs you can change:
  cost    = 55% of base price (a 45% gross margin, typical for D2C apparel)
  salvage = 20% of base price (what unsold stock eventually recovers)
Stock is expressed as WEEKS OF COVER at full price, so the results do not depend on one invented number.
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd

GRID = np.round(np.arange(0, 0.65, 0.05), 2)      # the discounts a merchandiser would actually consider


@dataclass
class Econ:
    cost_pct: float = 0.55
    salvage_pct: float = 0.20


def profit(x, stock, weeks, base_demand, elasticity, price, econ: Econ):
    demand = base_demand * (1 - x) ** elasticity
    sold = np.minimum(stock, weeks * demand)
    left = stock - sold
    cost, salv = econ.cost_pct * price, econ.salvage_pct * price
    return sold * (price * (1 - x) - cost) + left * (salv - cost), sold


def best_discount(stock, weeks, base_demand, elasticity, price, econ: Econ = Econ()):
    """Grid search: the discount with the highest expected gross profit."""
    p, _ = profit(GRID, stock, weeks, base_demand, elasticity, price, econ)
    return float(GRID[int(np.argmax(p))])


# ----------------------------------------------------------------- policies being compared
def policy_engine(row, weeks, econ):
    return best_discount(row.stock, weeks, row.base_demand, row.e_train, row.base_price, econ)


def policy_flat(rate):
    return lambda row, weeks, econ: rate


def policy_rule(row, weeks, econ):
    """The common merchandising rule of thumb: discount only slow movers, by a fixed amount.
    'Slow' = more stock than the season can absorb at full price."""
    cover = row.stock / max(row.base_demand, 1e-9)
    return 0.30 if cover > weeks else 0.0


POLICIES = {"no markdown": policy_flat(0.0), "flat 20% on everything": policy_flat(0.20),
            "flat 40% on everything": policy_flat(0.40), "rule of thumb: 30% on slow movers": policy_rule,
            "markdown engine (fitted elasticity)": policy_engine}


def backtest(skus: pd.DataFrame, weeks=8, cover_weeks=13, econ: Econ = Econ(), elasticity_error=1.0, seed=0):
    """Each SKU starts the final `weeks` of the season holding `cover_weeks` of stock at its full-price rate
    of sale. Stock is set independently of the season length, so a short season really is tighter.

    The honest part: each policy picks its discount using `e_train`, the elasticity fitted on EARLIER weeks,
    but profit is then realised against `e_true`, fitted on the whole period. So the engine is judged on
    decisions made with the information it would really have had.
    `elasticity_error` additionally stress-tests it: 1.3 means the true elasticity is 30% stronger than fitted.
    """
    rng = np.random.default_rng(seed)
    s = skus.copy()
    s["stock"] = np.ceil(cover_weeks * s.base_demand * rng.uniform(0.7, 1.3, len(s)))
    out = []
    for name, fn in POLICIES.items():
        disc = np.array([fn(r, weeks, econ) for r in s.itertuples()])
        e_true = s.e_true.values * elasticity_error
        gp, sold = profit(disc, s.stock.values, weeks, s.base_demand.values, e_true, s.base_price.values, econ)
        out.append({"policy": name, "avg_discount_pct": 100 * disc.mean(),
                    "skus_marked_down_pct": 100 * (disc > 0).mean(),
                    "gross_profit": gp.sum(), "units_sold": sold.sum(),
                    "sell_through_pct": 100 * sold.sum() / s.stock.sum(),
                    "leftover_units": s.stock.sum() - sold.sum()})
    r = pd.DataFrame(out)
    # Headline is vs the BEST FLAT discount, not vs no markdown: when stock is deep, doing nothing earns
    # almost nothing, and a ratio against a near-zero base produces meaningless four-digit percentages.
    # Reported as money per SKU, not as a ratio: when stock is deep and nothing is discounted, gross profit
    # goes NEGATIVE (leftover is written down below cost), and a percentage against a negative base is
    # meaningless or even flips sign. An earlier version of this table printed "+1,243%" for exactly that reason.
    best_flat = r[r.policy.str.startswith("flat")].gross_profit.max()
    n = len(s)
    r["gross_profit_per_sku"] = r.gross_profit / n
    r["vs_best_flat_per_sku"] = (r.gross_profit - best_flat) / n
    r["vs_no_markdown_per_sku"] = (r.gross_profit - r.gross_profit.iloc[0]) / n
    return r.round(2)


def metrics_table(skus: pd.DataFrame, weeks=8, cover_weeks=13, econ: Econ = Econ(), seed=0):
    """The engine's weekly output, in the merchandising metrics a buyer uses:
    ROS (rate of sale, units/week), cover (weeks of stock), STR (sell-through) and the recommended markdown."""
    rng = np.random.default_rng(seed)
    s = skus.copy()
    s["stock"] = np.ceil(cover_weeks * s.base_demand * rng.uniform(0.7, 1.3, len(s)))
    s["ros_units_per_week"] = s.base_demand.round(1)
    s["weeks_of_cover"] = (s.stock / s.base_demand).round(1)
    s["recommended_markdown_pct"] = [100 * best_discount(r.stock, weeks, r.base_demand, r.e_train, r.base_price, econ)
                                     for r in s.itertuples()]
    gp0, sold0 = profit(0.0, s.stock.values, weeks, s.base_demand.values, s.e_true.values, s.base_price.values, econ)
    gp1, sold1 = profit(s.recommended_markdown_pct.values / 100, s.stock.values, weeks, s.base_demand.values,
                        s.e_true.values, s.base_price.values, econ)
    s["str_no_markdown_pct"] = (100 * sold0 / s.stock).round(1)
    s["str_with_markdown_pct"] = (100 * sold1 / s.stock).round(1)
    s["gross_profit_gain"] = (gp1 - gp0).round(2)
    cols = ["desc", "base_price", "elasticity", "return_rate", "stock", "ros_units_per_week", "weeks_of_cover",
            "recommended_markdown_pct", "str_no_markdown_pct", "str_with_markdown_pct", "gross_profit_gain"]
    return s.rename(columns={"e_true": "elasticity"})[cols].sort_values("gross_profit_gain", ascending=False)
