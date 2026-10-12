"""Second-pass profiling: data-quality rules to drive ETL constraints & dictionary."""
import pandas as pd
import numpy as np

BASE = r"C:\Users\21597\.cache\kagglehub\competitions\challenge-01-spaghetti-schema-2026\Callenge Data Sets\Challenge_01_data_V1_0"

def load(name):
    return pd.read_csv(f"{BASE}\\{name}", dtype=str, keep_default_na=False)

p = load("products_2024.csv")
pr = load("promotions_2024.csv")
inv = load("inventory_snapshots_2024.csv")
s_all = pd.concat([load(f"sales_2024_q{q}.csv") for q in ["1","2","3","4"]], ignore_index=True)

def num(x): return pd.to_numeric(x, errors="coerce")

# 1) receipt-level fields constant per receipt?
print("=== receipt-level constancy ===")
for c in ["store_id","cashier_name","tender_type","customer_segment","sale_datetime"]:
    print(c, "-> nunique per receipt max:", s_all.groupby("receipt_id")[c].nunique().max())

# 2) weekend_flag vs actual date
print("\n=== weekend_flag correctness ===")
fmap = {
 "1": r"%m/%d/%Y %H:%M", "2": r"%Y-%m-%d %H:%M",
 "3": r"%d-%b-%Y %H:%M", "4": r"%m/%d/%y %I:%M %p"}
dt_all = []
for q, fmt in fmap.items():
    sub = load(f"sales_2024_q{q}.csv")
    d = pd.to_datetime(sub["sale_datetime"], format=fmt, errors="coerce")
    dt_all.append(d)
dt = pd.concat(dt_all, ignore_index=True)
s_all = s_all.copy()
s_all["_dt"] = dt
s_all["_is_weekend"] = s_all["_dt"].dt.dayofweek.isin([5,6])
s_all["_flag_bool"] = s_all["weekend_flag"].map({"True":True,"False":False})
print("weekend_flag mismatches:", (s_all["_is_weekend"] != s_all["_flag_bool"]).sum())
print("na datetimes:", s_all["_dt"].isna().sum())
print("date range:", dt.min(), "->", dt.max())

# 3) quantity stats
print("\n=== quantity ===")
print(s_all["quantity"].apply(num).describe())
print("quantity<=0 rows:", (num(s_all["quantity"])<=0).sum())

# 4) BOGO50 parity & promo price logic
print("\n=== promo price logic ===")
promo = s_all[s_all["promo_id"]!=""].copy()
promo["reg"]=num(promo["regular_price"]); promo["eff"]=num(promo["unit_price_effective"])
promo["qty"]=num(promo["quantity"]); promo["disc"]=num(promo["discount_percent_x"] if "discount_percent_x" in promo else 0)
promo = promo.assign(disc=promo["promo_id"].map(pr.set_index("promo_id")["discount_percent"].astype(float)))
for t in ["PCT_OFF","LOYALTY_PCT","BOGO50"]:
    sub = promo[promo["promo_type"]==t]
    print(f"--- {t}: n={len(sub)}")
    if t in ("PCT_OFF","LOYALTY_PCT"):
        expected = sub["reg"]*(1-sub["disc"]/100)
        print("  expected eff = reg*(1-disc/100), max abs diff:", (sub["eff"]-expected).abs().max())
    else:
        print("  qty values:", sorted(sub["qty"].unique())[:20], "| odd qty rows:", (sub["qty"]%2==1).sum())
        print("  eff vs reg: eff==reg?", (sub["eff"]==sub["reg"]).all(), "| eff==reg*0.5?", (sub["eff"]==sub["reg"]*0.5).all())
        print("  sample eff/reg:", (sub["eff"]/sub["reg"]).value_counts().to_dict())

# 5) tax logic
print("\n=== tax ===")
wellness = s_all[s_all["department_name"]=="Wellness"].copy()
wellness["tax"]=num(wellness["tax_amount"]); wellness["sub"]=num(wellness["line_subtotal"])
print("wellness tax rate (tax/subtotal) unique approx:", sorted(np.round(wellness["tax"]/wellness["sub"],4).unique()))
nonwell = s_all[s_all["department_name"]!="Wellness"]
print("non-wellness tax all zero:", (num(nonwell["tax_amount"])==0).all())

# 6) inventory value consistency
print("\n=== inventory ===")
inv["oh"]=num(inv["on_hand_qty"]); inv["uc"]=num(inv["unit_cost"]); inv["val"]=num(inv["inventory_cost_value"])
print("val == on_hand*unit_cost max diff:", (inv["val"]-inv["oh"]*inv["uc"]).abs().max())
print("inv unit_cost == products.unit_cost?", (inv.set_index("product_upc")["unit_cost"]==p.set_index("product_upc")["unit_cost"]).all())
print("on_hand min/max:", inv["oh"].min(), inv["oh"].max())

# 7) any empty/missing strings in key columns?
print("\n=== empty strings in sales key cols ===")
for c in ["receipt_id","product_upc","store_id","cashier_name","tender_type","customer_segment","quantity"]:
    print(c, "empty:", (s_all[c]=="").sum())

# 8) receipt line_number sequence integrity
print("\n=== line_number sequence ===")
g = s_all.groupby("receipt_id")["line_number"].agg(["min","max","count"])
print("receipts where min!=1:", (g["min"]!=1).sum(), "| max!=count:", (g["max"]!=g["count"]).sum())

# 9) dedupe check: same receipt+line+product?
print("\nsales dup (receipt,line_number):", s_all.duplicated(["receipt_id","line_number"]).sum())

# 10) product price/cost ranges for dictionary
print("\nproduct regular_price range:", num(p["regular_price"]).min(), num(p["regular_price"]).max())
print("product unit_cost range:", num(p["unit_cost"]).min(), num(p["unit_cost"]).max())
print("size/unit combo examples:")
print(p[["size","unit"]].drop_duplicates().to_string(index=False))