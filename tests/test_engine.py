import numpy as np
import pandas as pd

from elasticity import fit_sku, shrink
from markdown import Econ, best_discount, profit


def make_sku(e=-3.0, n=30, seed=0):
    """A SKU whose demand really does follow units = A * price^e, so the fit has a known right answer."""
    rng = np.random.default_rng(seed)
    price = rng.uniform(1.5, 3.0, n)
    units = 500 * price ** e * rng.lognormal(0, 0.05, n)
    return pd.DataFrame({"price": price, "units": units, "season": np.ones(n)})


def test_elasticity_recovers_a_known_value():
    e, r2, n, cv = fit_sku(make_sku(e=-3.0))
    assert abs(e - (-3.0)) < 0.25 and r2 > 0.9


def test_no_price_variation_gives_no_estimate():
    g = pd.DataFrame({"price": [2.0] * 20, "units": np.arange(20) + 10.0, "season": np.ones(20)})
    e, _, _, _ = fit_sku(g)
    assert np.isnan(e)


def test_shrinkage_pulls_short_histories_towards_the_average():
    f = pd.DataFrame({"elasticity": [-1.0, -9.0], "weeks_used": [40, 8]}, index=["long", "short"])
    s = shrink(f)
    long_shift = abs(s.loc["long", "elasticity_shrunk"] - (-1.0))
    short_shift = abs(s.loc["short", "elasticity_shrunk"] - (-9.0))
    assert short_shift > long_shift


def test_more_stock_than_the_season_can_absorb_earns_a_discount():
    econ = Econ()
    # 8 weeks left, sells 100/week at full price: 800 units will clear, 4,000 will not
    assert best_discount(stock=800, weeks=8, base_demand=100, elasticity=-3, price=10, econ=econ) == 0.0
    assert best_discount(stock=4000, weeks=8, base_demand=100, elasticity=-3, price=10, econ=econ) > 0.0


def test_a_price_insensitive_product_is_not_discounted_as_hard():
    econ = Econ()
    soft = best_discount(2500, 8, 100, -0.5, 10, econ)
    hard = best_discount(2500, 8, 100, -4.0, 10, econ)
    assert soft <= hard


def test_profit_never_counts_more_units_than_stock():
    gp, sold = profit(np.array([0.5]), stock=100, weeks=52, base_demand=1000, elasticity=-3, price=10, econ=Econ())
    assert sold[0] == 100
