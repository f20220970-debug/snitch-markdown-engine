"""python src/plot.py -> docs/results.png"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

R = Path(__file__).resolve().parents[1]
ev = pd.read_csv(R / "results" / "elasticity_validation.csv")
bt = pd.read_csv(R / "results" / "policy_comparison.csv")
sens = pd.read_csv(R / "results" / "sensitivity.csv")
el = pd.read_csv(R / "results" / "elasticities.csv")
fig, ax = plt.subplots(1, 4, figsize=(20, 4.6))

lbl = [m.replace("+ ", "").replace(" (shrunk)", "") for m in ev.model]
ax[0].barh(lbl, ev.mae_log_units, color=["#9aa5b1", "#9aa5b1", "#7fa8d8", "#1f4e79"])
ax[0].invert_yaxis(); ax[0].set_xlabel("prediction error on weeks never seen (lower is better)")
ax[0].set_title("1. Does price sensitivity predict demand?")

e = el.elasticity.dropna().clip(-12, 2)
ax[1].hist(e, bins=50, color="#1f4e79"); ax[1].axvline(-1, color="k", ls="--", lw=.9)
ax[1].text(-1.1, ax[1].get_ylim()[1]*.9, "   less sensitive →", fontsize=8)
ax[1].set_xlabel("price elasticity (more negative = discount lifts sales more)")
ax[1].set_title("2. Every product reacts differently")

b = bt.sort_values("gross_profit_per_sku")
cols = ["#2e7d32" if "engine" in p else "#9aa5b1" for p in b.policy]
ax[2].barh([p.replace(" on everything", "").replace(" (fitted elasticity)", "") for p in b.policy], b.gross_profit_per_sku, color=cols)
ax[2].set_xlabel("gross profit per product (8 weeks left, 13 weeks of stock)")
ax[2].set_title("3. Less discount, more profit")

ax[3].plot(sens.true_elasticity_vs_fitted, sens.vs_best_flat_per_sku, "o-", color="#2e7d32")
ax[3].axhline(0, color="k", lw=.8)
ax[3].set_xlabel("if true price sensitivity differs from the estimate")
ax[3].set_ylabel("profit per product vs the best flat discount")
ax[3].set_title("4. Still ahead when the estimate is wrong")
plt.tight_layout(); plt.savefig(R / "docs" / "results.png", dpi=130); print("saved")
