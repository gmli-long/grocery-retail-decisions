"""
Challenge 01 — EDA on the *normalized* schema.
Runs analytic SQL against the loaded database (proving the schema is queryable),
produces the 6 figures used in the report/deck/notebook, and prints headline
numbers for the write-up.
"""
import sqlite3
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

BASE = Path(__file__).resolve().parent.parent
DB = BASE / "data" / "challenge_01.sqlite"
FIG = BASE / "reports" / "figures"
FIG.mkdir(parents=True, exist_ok=True)

plt.rcParams.update({"figure.dpi": 110, "axes.grid": True, "grid.alpha": 0.3,
                     "axes.spines.top": False, "axes.spines.right": False,
                     "font.size": 10})

PALETTE = ["#2c7fb8", "#41b6c4", "#7fcdbb", "#c7e9b4", "#edf8b1", "#feb24c",
           "#f03b20", "#756bb1"]

conn = sqlite3.connect(DB)


def q(sql, params=()):
    return pd.read_sql_query(sql, conn, params=params)


print("=" * 60)
print("EDA on the normalized schema")
print("=" * 60)

# ---- 1. Revenue by department ---------------------------------------------
rev_dept = q("""
SELECT d.department_name AS department,
       SUM(li.line_subtotal) AS revenue,
       COUNT(*) AS units
FROM line_items li
JOIN products p ON p.product_upc = li.product_upc
JOIN categories c ON c.category_id = p.category_id
JOIN departments d ON d.department_id = c.department_id
GROUP BY d.department_name
ORDER BY revenue DESC
""")
print("\nRevenue by department:")
print(rev_dept.to_string(index=False))
print("TOTAL revenue: %.2f  TOTAL units: %d" % (rev_dept.revenue.sum(), rev_dept.units.sum()))

fig, ax = plt.subplots(figsize=(8, 4.2))
colors = [PALETTE[i % len(PALETTE)] for i in range(len(rev_dept))]
ax.barh(rev_dept.department[::-1], rev_dept.revenue[::-1] / 1e3,
        color=colors[::-1])
ax.set_xlabel("Revenue (thousand $)")
ax.set_title("Revenue by department (2024)")
for i, v in enumerate(rev_dept.revenue[::-1]):
    ax.text(v / 1e3 + 1, i, f"${v/1e3:.0f}k", va="center", fontsize=9)
plt.tight_layout()
plt.savefig(FIG / "fig1_department_revenue.png", bbox_inches="tight")
plt.close()

# ---- 2. Monthly revenue trend (with promo share) ---------------------------
monthly = q("""
SELECT strftime('%m', r.sale_datetime) AS month,
       SUM(li.line_subtotal) AS revenue,
       SUM(CASE WHEN li.promo_id IS NOT NULL THEN li.line_subtotal ELSE 0 END) AS promo_rev
FROM line_items li
JOIN receipts r ON r.receipt_id = li.receipt_id
GROUP BY month ORDER BY month
""")
monthly["promo_share"] = 100 * monthly.promo_rev / monthly.revenue
print("\nMonthly revenue / promo share:")
print(monthly.to_string(index=False))

fig, ax1 = plt.subplots(figsize=(8, 4))
ax1.bar(monthly.month, monthly.revenue / 1e3, color="#41b6c4", label="Revenue")
ax1.set_xlabel("Month"); ax1.set_ylabel("Revenue (thousand $)", color="#1b4f72")
ax1.tick_params(axis="y", labelcolor="#1b4f72")
ax2 = ax1.twinx()
ax2.plot(monthly.month, monthly.promo_share, color="#f03b20", marker="o", label="Promo share")
ax2.set_ylabel("Promo revenue share (%)", color="#f03b20")
ax2.tick_params(axis="y", labelcolor="#f03b20")
ax2.set_ylim(0, 30)
ax1.set_title("Monthly revenue and promotional share")
plt.tight_layout()
plt.savefig(FIG / "fig2_monthly_trend.png", bbox_inches="tight")
plt.close()

# ---- 3. Store performance (by segment mix) ---------------------------------
store_seg = q("""
SELECT s.store_name AS store, r.customer_segment AS segment,
       SUM(li.line_subtotal) AS revenue, COUNT(DISTINCT r.receipt_id) AS receipts
FROM receipts r
JOIN stores s ON s.store_id = r.store_id
JOIN line_items li ON li.receipt_id = r.receipt_id
GROUP BY s.store_name, r.customer_segment ORDER BY s.store_name
""")
piv = store_seg.pivot(index="store", columns="segment", values="revenue").fillna(0)
print("\nStore x segment revenue:")
print(piv.to_string())

fig, ax = plt.subplots(figsize=(7, 4.2))
piv[["Member", "Non-Member"]].plot(kind="bar", ax=ax, stacked=True,
                                   color=["#2c7fb8", "#c7e9b4"])
ax.set_ylabel("Revenue ($)")
ax.set_title("Store performance by customer segment")
ax.set_xticklabels(ax.get_xticklabels(), rotation=0)
ax.legend(title="Segment")
plt.tight_layout()
plt.savefig(FIG / "fig3_store_segment.png", bbox_inches="tight")
plt.close()

# ---- 4. Promo lift (avg line $ and basket qty, promo vs not) --------------
promo_lift = q("""
SELECT COALESCE(pr.promo_type,'NO_PROMO') AS promo_type,
       AVG(li.unit_price_effective) AS avg_price,
       SUM(li.quantity) * 1.0 / COUNT(*) AS avg_qty_per_line,
       SUM(li.line_subtotal) AS revenue,
       COUNT(*) AS lines
FROM line_items li
LEFT JOIN promotions pr ON pr.promo_id = li.promo_id
GROUP BY pr.promo_type ORDER BY revenue DESC
""")
promo_lift["avg_line_rev"] = promo_lift.revenue / promo_lift.lines
print("\nPromo lift summary:")
print(promo_lift.to_string(index=False))

order = ["PCT_OFF", "LOYALTY_PCT", "BOGO50", "NO_PROMO"]
lift = promo_lift.set_index("promo_type").reindex(order)
fig, ax = plt.subplots(figsize=(7, 4.2))
x = np.arange(len(lift))
ax.bar(x, lift.avg_line_rev, color=["#2c7fb8", "#41b6c4", "#7fcdbb", "#d9d9d9"])
ax.set_xticks(x); ax.set_xticklabels(lift.index)
ax.set_ylabel("Avg revenue per line ($)")
ax.set_title("Average line revenue by promotion type")
plt.tight_layout()
plt.savefig(FIG / "fig4_promo_lift.png", bbox_inches="tight")
plt.close()

# ---- 5. Member vs non-member mix ------------------------------------------
memb = q("""
SELECT r.customer_segment AS segment,
       COUNT(DISTINCT r.receipt_id) AS receipts,
       SUM(li.line_subtotal) AS revenue,
       SUM(li.line_subtotal)*1.0/COUNT(DISTINCT r.receipt_id) AS basket_value
FROM receipts r JOIN line_items li ON li.receipt_id = r.receipt_id
GROUP BY r.customer_segment
""")
print("\nMember vs non-member:")
print(memb.to_string(index=False))

fig, (a1, a2) = plt.subplots(1, 2, figsize=(8, 3.8))
a1.pie(memb.revenue, labels=memb.segment, autopct="%.0f%%",
       colors=["#2c7fb8", "#c7e9b4"], startangle=90)
a1.set_title("Revenue share")
a2.bar(memb.segment, memb.basket_value, color=["#2c7fb8", "#c7e9b4"])
a2.set_ylabel("Avg basket value ($)")
a2.set_title("Basket value")
for i, v in enumerate(memb.basket_value):
    a2.text(i, v + 0.3, f"${v:.2f}", ha="center")
plt.tight_layout()
plt.savefig(FIG / "fig5_member_mix.png", bbox_inches="tight")
plt.close()

# ---- 6. Top 10 products by revenue ----------------------------------------
top = q("""
SELECT p.product_name, d.department_name AS dept, SUM(li.line_subtotal) AS revenue
FROM line_items li JOIN products p ON p.product_upc = li.product_upc
JOIN categories c ON c.category_id = p.category_id
JOIN departments d ON d.department_id = c.department_id
GROUP BY p.product_name, d.department_name
ORDER BY revenue DESC LIMIT 10
""")
print("\nTop 10 products by revenue:")
print(top.to_string(index=False))

fig, ax = plt.subplots(figsize=(8, 4.2))
ax.barh(top.product_name[::-1], top.revenue[::-1] / 1e3, color="#2c7fb8")
ax.set_xlabel("Revenue (thousand $)")
ax.set_title("Top 10 products by revenue")
plt.tight_layout()
plt.savefig(FIG / "fig6_top_products.png", bbox_inches="tight")
plt.close()

conn.close()
print("\nFigures written to", FIG)