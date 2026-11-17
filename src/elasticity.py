"""How much more does a product sell when it is discounted? (price elasticity, per SKU)

Model, per SKU:   log(units) = a + e * log(price) + s * log(store-wide demand index that week)
`e` is the price elasticity: e = -2 means a 10% price cut sells about 21% more units.
The seasonality term stops a Christmas rush being read as a price effect.

This is observational, not an experiment: prices here were not set at random, so `e` is an estimate of an
association, and the honest next step at a real retailer is a price test. What IS tested here is whether
the fitted elasticity predicts demand in weeks the model never saw, against three baselines.
"""
import numpy as np
import pandas as pd

MIN_PRICE_CV = 0.03        # no usable price variation -> no elasticity can be estimated


def fit_sku(g: pd.DataFrame):
    """OLS of log units on log price and log seasonality for one SKU. Returns (elasticity, r2, n, price_cv)."""
    cv = g.price.std() / g.price.mean() if len(g) > 2 else 0.0
    if len(g) < 8 or cv < MIN_PRICE_CV:
        return np.nan, np.nan, len(g), cv
    X = np.column_stack([np.ones(len(g)), np.log(g.price.values), np.log(g.season.values)])
    y = np.log(g.units.values)
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    ss_tot = ((y - y.mean()) ** 2).sum()
    r2 = 1 - (resid ** 2).sum() / ss_tot if ss_tot > 0 else np.nan
    return float(beta[1]), float(r2), len(g), float(cv)


def fit_all(panel: pd.DataFrame, weeks_train=None) -> pd.DataFrame:
    """Fit one elasticity per SKU, optionally using only the first `weeks_train` weeks."""
    p = panel if weeks_train is None else panel[panel.week_index <= weeks_train]
    rows = []
    for sku, g in p.groupby("StockCode"):
        e, r2, n, cv = fit_sku(g)
        rows.append({"StockCode": sku, "elasticity": e, "r2": r2, "weeks_used": n, "price_cv": cv,
                     "mean_units": g.units.mean(), "mean_price": g.price.mean()})
    return pd.DataFrame(rows).set_index("StockCode")


def shrink(fits: pd.DataFrame, k: float = 10.0) -> pd.DataFrame:
    """Pull noisy per-SKU estimates towards the overall average (empirical-Bayes style shrinkage):
    a SKU with 8 noisy weeks should not be trusted as much as one with 40. Weight = n / (n + k)."""
    f = fits.copy()
    ok = f.elasticity.notna()
    grand = f.loc[ok, "elasticity"].median()
    w = f.weeks_used / (f.weeks_used + k)
    f["elasticity_shrunk"] = np.where(ok, w * f.elasticity + (1 - w) * grand, grand)
    f["grand_mean_elasticity"] = grand
    return f


def evaluate(panel: pd.DataFrame, split_week: int) -> pd.DataFrame:
    """Fit on weeks <= split_week, predict units in later weeks, and compare with three baselines.
    Error is mean absolute error in log units (so it is a relative error, comparable across SKUs)."""
    fits = shrink(fit_all(panel, weeks_train=split_week))
    train = panel[panel.week_index <= split_week]
    test = panel[panel.week_index > split_week].copy()
    base = train.groupby("StockCode").agg(mu=("units", "mean"), lmu=("units", lambda s: np.log(s).mean()),
                                          lp=("price", lambda s: np.log(s).mean()),
                                          ls=("season", lambda s: np.log(s).mean()))
    test = test.join(base, on="StockCode").join(fits[["elasticity_shrunk", "elasticity"]], on="StockCode")
    test = test.dropna(subset=["lmu"])
    ly = np.log(test.units.values)
    preds = {
        "SKU average (no price, no season)": test.lmu.values,
        "+ seasonality only": test.lmu.values + (np.log(test.season.values) - test.ls.values),
        "+ one elasticity for all SKUs": test.lmu.values + fits.grand_mean_elasticity.iloc[0] * (np.log(test.price.values) - test.lp.values)
                                          + (np.log(test.season.values) - test.ls.values),
        "+ per-SKU elasticity (shrunk)": test.lmu.values + test.elasticity_shrunk.values * (np.log(test.price.values) - test.lp.values)
                                          + (np.log(test.season.values) - test.ls.values),
    }
    rows = []
    for name, pr in preds.items():
        rows.append({"model": name, "mae_log_units": float(np.mean(np.abs(pr - ly))),
                     "median_abs_pct_error": float(np.median(np.abs(np.expm1(pr - ly)))) * 100})
    out = pd.DataFrame(rows)
    out["improvement_vs_sku_average_pct"] = 100 * (1 - out.mae_log_units / out.mae_log_units.iloc[0])
    return out.round(3), fits, int(len(test))
