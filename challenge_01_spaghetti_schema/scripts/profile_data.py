"""Data profiling script: reverse-engineer entities, keys, and inconsistencies."""
import pandas as pd
import numpy as np
import io, sys

BASE = r"C:\Users\21597\.cache\kagglehub\competitions\challenge-01-spaghetti-schema-2026\Callenge Data Sets\Challenge_01_data_V1_0"

def load(name):
    df = pd.read_csv(f"{BASE}\\{name}", dtype=str, keep_default_na=False)
    return df

def sec(title):
    print("\n" + "="*70)
    print(title)
    print("="*70)

# ---- Products ----
sec("PRODUCTS")
p = load("products_2024.csv")
print("shape:", p.shape)
print("dup upc:", p["product_upc"].duplicated().sum())
print("cols:", list(p.columns))
print("distinct vendors:", p["vendor_name"].nunique(), "| distinct depts:", p["department_name"].nunique(),
      "| distinct categories:", p["category_name"].nunique(), "| distinct brands:", p["brand"].nunique())
print("depts:", sorted(p["department_name"].unique()))
print("brands:", sorted(p["brand"].unique()))
print("vendors count:", p["vendor_name"].nunique(), "(phones)", p["vendor_phone"].nunique())
# vendor -> phone mapping consistency
vmap = p.groupby("vendor_name")["vendor_phone"].nunique()
print("vendors with >1 phone:", (vmap>1).sum())
print("empty vendor_phone:", (p["vendor_phone"]=="").sum())
print("empty size/unit examples:", p[p["size"]==""].shape, p[p["unit"]==""].shape)
print("regular_price/unit_cost sample:", p["regular_price"].head(3).tolist(), p["unit_cost"].head(3).tolist())
print("pack_size unique:", sorted(p["pack_size"].unique()))

# ---- Promotions ----
sec("PROMOTIONS")
pr = load("promotions_2024.csv")
print("shape:", pr.shape)
print("dup promo_id:", pr["promo_id"].duplicated().sum())
print("promo_type values:", pr["promo_type"].value_counts().to_dict())
print("upc all in products?", pr["product_upc"].isin(p["product_upc"]).all(), "| missing:", (~pr["product_upc"].isin(p["product_upc"])).sum())
print("discount_percent unique:", sorted(pr["discount_percent"].unique()))
print("start_date min/max:", pr["start_date"].min(), pr["end_date"].max())
# duplicated product info consistency
mismatch_name = pr[pr["product_upc"].map(p.set_index("product_upc")["product_name"]) != pr["product_name"]]
print("promo product_name mismatch vs products:", mismatch_name.shape[0])
mismatch_dept = pr[pr["product_upc"].map(p.set_index("product_upc")["department_name"]) != pr["department_name"]]
print("promo dept mismatch:", mismatch_dept.shape[0])

# ---- Inventory ----
sec("INVENTORY")
inv = load("inventory_snapshots_2024.csv")
print("shape:", inv.shape)
print("distinct stores:", inv["store_id"].nunique(), "| distinct upc:", inv["product_upc"].nunique())
print("snapshot_dates:", sorted(inv["snapshot_date"].unique()))
print("stores full list:", sorted(inv["store_id"].unique()))
# store attribute consistency
smismatch = inv.groupby("store_id")[["store_name","store_address","store_city","store_state","store_zip"]].nunique()
print("stores with inconsistent attrs (max nunique>1):", (smismatch.max(axis=1)>1).sum())
print("inv upc all in products?", inv["product_upc"].isin(p["product_upc"]).all(), "| missing:", (~inv["product_upc"].isin(p["product_upc"])).sum())

# ---- Sales ----
sec("SALES")
rows = []
for q in ["q1","q2","q3","q4"]:
    s = load(f"sales_2024_{q}.csv")
    rows.append(s)
    print(f"--- {q}: shape {s.shape}, receipt_id nunique {s['receipt_id'].nunique()}")

s_all = pd.concat(rows, ignore_index=True)
print("\nTOTAL sales rows:", s_all.shape[0])
print("receipt_id distinct:", s_all["receipt_id"].nunique())
print("line_number max per receipt:", s_all.groupby("receipt_id")["line_number"].max().max())
print("distinct stores in sales:", s_all["store_id"].nunique())
print("distinct upc in sales:", s_all["product_upc"].nunique())
print("sales upc all in products?", s_all["product_upc"].isin(p["product_upc"]).all(), "| missing:", (~s_all["product_upc"].isin(p["product_upc"])).sum())
print("cashiers:", sorted(s_all["cashier_name"].unique()))
print("tender types:", s_all["tender_type"].value_counts().to_dict())
print("segments:", s_all["customer_segment"].value_counts().to_dict())
print("promo_type in sales:", sorted(s_all["promo_type"].unique()))
print("weekend_flag:", s_all["weekend_flag"].value_counts().to_dict())

# consistency: product attributes repeated on every line vs products master
mcol = {"product_name":"product_name","brand":"brand","department_name":"department_name",
        "category_name":"category_name","size":"size","unit":"unit",
        "vendor_name":"vendor_name","vendor_phone":"vendor_phone","pack_size":"pack_size",
        "regular_price":"regular_price","unit_cost":"unit_cost"}
pmap = p.set_index("product_upc")
for c in mcol:
    ref = s_all["product_upc"].map(pmap[c])
    nm = (ref != s_all[c]).sum()
    print(f"sales {c}: mismatch vs products = {nm} ({100*nm/len(s_all):.2f}%)")

# promo_id consistency
print("\n-- promo integrity in sales --")
has_promo = s_all[s_all["promo_id"] != ""]
print("rows with promo_id:", has_promo.shape[0])
print("promo_id in promotions file?", has_promo["promo_id"].isin(pr["promo_id"]).all(), "| missing:", (~has_promo["promo_id"].isin(pr["promo_id"])).sum())
print("rows with promo_type but empty promo_id:", ((s_all["promo_type"]!="") & (s_all["promo_id"]=="")).sum())
print("rows with promo_id but empty promo_type:", ((s_all["promo_id"]!="") & (s_all["promo_type"]=="")).sum())

# tax logic
sec("TAX & PRICE LOGIC")
print("tax_amount unique:", sorted(s_all["tax_amount"].unique()))
dep_tax = s_all.groupby("department_name")["tax_amount"].apply(lambda x: pd.to_numeric(x, errors="coerce").nunique())
print("tax distinct per dept:", dep_tax.to_dict())
# line_subtotal check
def num(x): return pd.to_numeric(x, errors="coerce")
sub_ok = (num(s_all["line_subtotal"]) - (num(s_all["unit_price_effective"]) * num(s_all["quantity"]))).abs()
print("max |line_subtotal - price*qty|:", sub_ok.max(), "rows off > .01:", (sub_ok>0.01).sum())

# Q4 12hr parsing ambiguity note (year 2024)
print("\nQ4 midnight PM example rows:")
q4 = rows[3]
print(q4[q4["sale_datetime"].str.contains("AM|PM", na=False)]["sale_datetime"].head(2).tolist())