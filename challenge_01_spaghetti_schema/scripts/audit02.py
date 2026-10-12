"""Challenge 02 — data audit: find every injected error across the 5 CSVs."""
import pandas as pd
import numpy as np

D = r"C:\Users\21597\.cache\kagglehub\competitions\challenge-02-errors-integrity-2026\challenge_02_data"

def load(n):
    return pd.read_csv(f"{D}\\{n}", dtype=str, keep_default_na=False)

def sec(t):
    print("\n" + "="*64 + "\n" + t + "\n" + "="*64)

products  = load("products.csv")
vendors   = load("vendors.csv")
stores    = load("stores.csv")
categories= load("categories.csv")
sales     = load("sales.csv")

sec("BASIC SHAPES")
for n, df in [("products", products), ("vendors", vendors), ("stores", stores),
              ("categories", categories), ("sales", sales)]:
    print(f"{n}: {df.shape}  cols={list(df.columns)}")

sec("1) PRODUCTS")
print("dup product_id:", products['product_id'].duplicated().sum())
print("dup sku:", products['sku'].duplicated().sum())
print("empty name:", (products['name']=='').sum(), "| empty sku:", (products['sku']=='').sum())
print("category_id values:", sorted(products['category_id'].unique()))
print("vendor_id values:", sorted(products['vendor_id'].unique()))
print("category_id orphans (not in categories):",
      set(products['category_id']) - set(categories['category_id']))
print("vendor_id orphans (not in vendors):",
      set(products['vendor_id']) - set(vendors['vendor_id']))

sec("2) VENDORS")
print("dup vendor_id:", vendors['vendor_id'].duplicated().sum())
print("dup name:", vendors['name'].duplicated().sum())
print(vendors.to_string(index=False))

sec("3) STORES")
print("dup store_id:", stores['store_id'].duplicated().sum())
print("dup name:", stores['name'].duplicated().sum())
print("empty city:", (stores['city']=='').sum())
print(stores.to_string(index=False))

sec("4) CATEGORIES")
print("dup category_id:", categories['category_id'].duplicated().sum())
print("dup name:", categories['name'].duplicated().sum())
print(categories.to_string(index=False))

sec("5) SALES — shape & missing")
print("shape:", sales.shape)
print("missing per col:")
print((sales == '').sum())
print("\nstore_id values:", sorted(sales['store_id'].unique()))
print("product_id values:", sorted(sales['product_id'].unique()))
print("store_id orphans:", set(sales['store_id']) - set(stores['store_id']))
print("product_id orphans:", set(sales['product_id']) - set(products['product_id']))

sec("6) SALES — duplicates")
print("full-row duplicate count:", sales.duplicated().sum())
print("dup txn_id count:", sales['txn_id'].duplicated().sum())
dups = sales[sales['txn_id'].duplicated(keep=False)]
print("rows sharing a txn_id:", len(dups))

sec("7) SALES — txn_date / drift")
d = pd.to_datetime(sales['txn_date'], errors='coerce')
print("unparseable dates:", d.isna().sum())
print("min:", d.min(), " max:", d.max())
# future / out-of-2024 dates
print("counts by year:")
print(d.dt.year.value_counts().sort_index())

sec("8) SALES — numeric sanity")
def num(x): return pd.to_numeric(x, errors='coerce')
qty = num(sales['qty']); price = num(sales['unit_price']); amt = num(sales['line_amount'])
print("qty: nan=", qty.isna().sum(), " min=", qty.min(), " max=", qty.max())
print("qty <= 0:", (qty<=0).sum(), "| qty==0:", (qty==0).sum())
print("unit_price: nan=", price.isna().sum(), " min=", price.min(), " max=", price.max())
print("unit_price <= 0:", (price<=0).sum())
print("line_amount: nan=", amt.isna().sum(), " min=", amt.min(), " max=", amt.max())
calc = (qty * price)
diff = (amt - calc).abs()
print("line_amount vs qty*price: max abs diff =", diff.max(), " rows off >0.01:", (diff>0.01).sum())

sec("9) qty & price distribution (outlier spikes)")
print("qty value counts:")
print(qty.value_counts().sort_index().head(20))
print("\nunit_price describe:")
print(price.describe())