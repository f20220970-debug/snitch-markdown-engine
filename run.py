"""Run everything: python run.py  ->  results/*.csv, results/summary.json  (~2 min)"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
import data as D                                  # noqa: E402
import elasticity as E                            # noqa: E402
import markdown as M                              # noqa: E402

RES = ROOT / "results"
RES.mkdir(exist_ok=True)
SPLIT = 40                                        # weeks 1-40 to learn from, 41-53 held out


def main():
    panel, info = D.load()
    S = {"transaction_lines": 541909, "skus_analysed": int(panel.StockCode.nunique()),
         "sku_weeks": int(len(panel)), "weeks": int(panel.week_index.max()),
         "weeks_train": SPLIT, "weeks_held_out": int(panel.week_index.max() - SPLIT)}

    # 1. does knowing a SKU's price sensitivity predict demand in weeks the model never saw?
    ev, fits_train, n_test = E.evaluate(panel, split_week=SPLIT)
    ev.to_csv(RES / "elasticity_validation.csv", index=False)
    S["held_out_sku_weeks"] = n_test
    S["error_reduction_vs_sku_average_pct"] = float(ev.improvement_vs_sku_average_pct.iloc[-1])

    # 2. the elasticities themselves
    fits_all = E.shrink(E.fit_all(panel))
    e = fits_all.elasticity.dropna()
    S["elasticity"] = {"skus_estimated": int(len(e)), "median": round(float(e.median()), 2),
                       "p10": round(float(e.quantile(0.1)), 2), "p90": round(float(e.quantile(0.9)), 2),
                       "share_negative_pct": round(100 * float((e < 0).mean()), 1)}
    fits_all.round(3).to_csv(RES / "elasticities.csv")

    # 3. per-SKU table the policy runs on
    base = panel[panel.discount <= 0.05].groupby("StockCode").units.mean().rename("base_demand")
    skus = (info.join(base).join(fits_all[["elasticity_shrunk"]].rename(columns={"elasticity_shrunk": "e_true"}))
                .join(fits_train[["elasticity_shrunk"]].rename(columns={"elasticity_shrunk": "e_train"})))
    skus = skus.dropna(subset=["base_demand", "e_true", "e_train"])
    skus = skus[(skus.base_demand > 1) & (skus.e_true < -0.2)]        # need a downward-sloping demand curve
    S["skus_in_backtest"] = int(len(skus))

    # 4. the comparison
    bt = M.backtest(skus)
    bt.to_csv(RES / "policy_comparison.csv", index=False)
    S["policy_comparison"] = bt.to_dict(orient="records")

    # 5. sensitivity: what if the fitted elasticity is wrong?
    rows = []
    for err in [0.6, 0.8, 1.0, 1.2, 1.4]:
        b = M.backtest(skus, elasticity_error=err)
        eng = b[b.policy.str.startswith("markdown engine")].iloc[0]
        rows.append({"true_elasticity_vs_fitted": f"{err:.0%}",
                     "engine_profit_per_sku": eng.gross_profit_per_sku,
                     "vs_best_flat_per_sku": eng.vs_best_flat_per_sku,
                     "engine_avg_discount_pct": eng.avg_discount_pct})
    sens = pd.DataFrame(rows)
    sens.to_csv(RES / "sensitivity.csv", index=False)
    S["sensitivity"] = sens.to_dict(orient="records")

    # 6. season length and stock depth
    rows = []
    for weeks in [4, 8, 12]:
        for cw in [8, 13, 20]:
            b = M.backtest(skus, weeks=weeks, cover_weeks=cw)
            eng = b[b.policy.str.startswith("markdown engine")].iloc[0]
            rows.append({"weeks_left": weeks, "weeks_of_stock": cw,
                         "engine_profit_per_sku": eng.gross_profit_per_sku,
                         "no_markdown_profit_per_sku": b.gross_profit_per_sku.iloc[0],
                         "best_flat_profit_per_sku": b[b.policy.str.startswith("flat")].gross_profit_per_sku.max(),
                         "engine_avg_discount_pct": eng.avg_discount_pct,
                         "engine_sell_through_pct": eng.sell_through_pct})
    sc = pd.DataFrame(rows).round(2)
    sc.to_csv(RES / "scenarios.csv", index=False)
    S["scenarios"] = sc.to_dict(orient="records")

    # 7. the weekly markdown list
    tab = M.metrics_table(skus)
    tab.round(3).to_csv(RES / "markdown_list.csv")
    S["returns"] = {"overall_return_rate_pct": round(100 * float(info.returned.sum() / info.units.sum()), 2),
                    "skus_over_10pct_returns": int((info.return_rate > 0.10).sum()),
                    "share_of_returned_units_from_those_skus_pct": round(
                        100 * float(info.loc[info.return_rate > 0.10, "returned"].sum() / info.returned.sum()), 1)}
    (RES / "summary.json").write_text(json.dumps(S, indent=1, default=float))
    pd.set_option("display.width", 200)
    print(json.dumps({k: v for k, v in S.items() if not isinstance(v, list)}, indent=1, default=float))
    print("\n== demand model, held-out weeks\n", ev.to_string(index=False))
    print("\n== policy comparison (8 weeks left, 13 weeks of stock)\n", bt.to_string(index=False))
    print("\n== if the fitted elasticity is wrong\n", sens.to_string(index=False))
    print("\n== scenarios\n", sc.to_string(index=False))
    print("\n== top of the markdown list\n", tab.head(8).to_string())


if __name__ == "__main__":
    main()
