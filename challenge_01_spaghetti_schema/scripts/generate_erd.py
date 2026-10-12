"""Render the conceptual ERD (crow's-foot style) to docs/erd.png and
reports/figures/erd.png using matplotlib only (no external graphviz dep)."""
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

BASE = Path(__file__).resolve().parent.parent
OUT = [BASE / "docs" / "erd.png", BASE / "reports" / "figures" / "erd.png"]
for o in OUT:
    o.parent.mkdir(parents=True, exist_ok=True)

# entity: (name, [fields...], x, y)
# fields: (name, "PK"/"FK"/"")  -> we render key marker
ENT = [
    ("departments", ["department_id (PK)", "department_name"], 0.0, 6.9),
    ("categories",   ["category_id (PK)", "department_id (FK)", "category_name"], 2.6, 6.9),
    ("brands",       ["brand_id (PK)", "brand_name"], 0.0, 5.2),
    ("vendors",      ["vendor_id (PK)", "vendor_name", "vendor_phone"], 0.0, 3.6),
    ("stores",       ["store_id (PK)", "store_name", "address/city/state/zip"], 0.0, 1.7),
    ("cashiers",     ["cashier_id (PK)", "cashier_name"], 0.0, 0.1),
    ("products",     ["product_upc (PK)", "brand_id (FK)", "category_id (FK)",
                      "vendor_id (FK)", "size · unit · pack_size",
                      "regular_price · unit_cost"], 4.3, 4.4),
    ("promotions",   ["promo_id (PK)", "product_upc (FK)", "promo_type",
                      "discount_percent", "start_date · end_date"], 8.4, 6.6),
    ("receipts",     ["receipt_id (PK)", "store_id (FK)", "cashier_id (FK)",
                      "sale_datetime", "tender_type", "customer_segment"], 8.4, 4.2),
    ("line_items",   ["line_item_id (PK)", "receipt_id (FK)", "product_upc (FK)",
                      "promo_id (FK, NULL)", "quantity", "unit_price_effective",
                      "line_subtotal · tax_amount"], 8.4, 2.0),
    ("inventory_snapshots", ["snapshot_id (PK)", "store_id (FK)", "product_upc (FK)",
                             "snapshot_date", "on_hand_qty"], 8.4, 0.1),
]

# relationships: (a_name, b_name, "1"/"N" at a, "1"/"N" at b)
REL = [
    ("departments", "categories", "1", "N"),
    ("categories", "products", "1", "N"),
    ("brands", "products", "1", "N"),
    ("vendors", "products", "1", "N"),
    ("stores", "receipts", "1", "N"),
    ("stores", "inventory_snapshots", "1", "N"),
    ("cashiers", "receipts", "1", "N"),
    ("products", "promotions", "1", "N"),
    ("products", "line_items", "1", "N"),
    ("products", "inventory_snapshots", "1", "N"),
    ("receipts", "line_items", "1", "N"),
    ("promotions", "line_items", "1", "N"),
]

pos = {e[0]: (e[2], e[3]) for e in ENT}
FIELDS = {e[0]: e[1] for e in ENT}

fig, ax = plt.subplots(figsize=(13.2, 8.2))
ax.set_xlim(-0.6, 12.8)
ax.set_ylim(-0.6, 8.0)
ax.axis("off")

BW, BH = 2.5, 0.32       # box width, per-field height
DIM_COLOR, FACT_COLOR = "#eaf2f8", "#fef5e7"
EDGE = "#2c3e50"

def draw_box(name, x, y, color):
    fields = FIELDS[name]
    h = len(fields) * BH + 0.34
    box = FancyBboxPatch((x, y), BW, h, boxstyle="round,pad=0.02",
                         fc=color, ec=EDGE, lw=1.1)
    ax.add_patch(box)
    ax.text(x + BW/2, y + h - 0.22, name, ha="center", va="center",
            fontsize=10, fontweight="bold")
    for i, f in enumerate(fields):
        ax.text(x + 0.12, y + h - 0.50 - i*BH, f, ha="left", va="center",
                fontsize=8.0)
    return x + BW/2, y + h/2, h   # return center

centers = {}
for name, _, x, y in ENT:
    is_dim = name in ("departments", "categories", "brands", "vendors",
                      "stores", "cashiers")
    cx, cy, h = draw_box(name, x, y, DIM_COLOR if is_dim else FACT_COLOR)
    centers[name] = (cx, cy)

# draw relationship lines with cardinality labels
for a, b, ca, cb in REL:
    x1, y1 = centers[a]
    x2, y2 = centers[b]
    ax.plot([x1, x2], [y1, y2], color="#7f8c8d", lw=1.0, zorder=0)
    # label near each end
    dx, dy = x2 - x1, y2 - y1
    L = (dx*dx + dy*dy) ** 0.5 or 1
    ux, uy = dx / L, dy / L
    ax.text(x1 + ux*0.55, y1 + uy*0.55 + 0.12, ca, fontsize=9, color="#c0392b",
            ha="center", fontweight="bold")
    ax.text(x2 - ux*0.55, y2 - uy*0.55 + 0.12, cb, fontsize=9, color="#c0392b",
            ha="center", fontweight="bold")

ax.text(6.2, 7.7, "Normalized relational schema (3NF) — Challenge 01",
        fontsize=13, fontweight="bold", ha="center")
ax.text(6.2, 7.35, "dimensions (blue)  ·  facts (amber)  ·  crow's-foot: 1 → N",
        fontsize=9, ha="center", color="#555")

plt.tight_layout()
for o in OUT:
    plt.savefig(o, bbox_inches="tight", dpi=150)
plt.close()
print("ERD written to", [str(o) for o in OUT])