"""Challenge 02 — precise characterization of each injected error class."""
import pandas as pd
import numpy as np

D = r"C:\Users\21597\.cache\kagglehub\competitions\challenge-02-errors-integrity-2026\challenge_02_data"
def load(n): return pd.read_csv(f"{D}\\{n}", dtype=str, keep_default_na=False)
def num(x): return pd.to_numeric(x, errors='coerce')

products = load("products.csv"); vendors = load("vendors.csv")
stores = load("stores.csv"); categories = load("categories.csv")
sales = load("sales.csv")

print("== txn_date: empty vs malformed ==")
empty = (sales['txn_date'] == '')
d = pd.to_datetime(sales['txn_date'], errors='coerce')
malformed = (~empty) & d.isna()
print("empty txn_date:", empty.sum(), "| non-empty but unparseable:", malformed.sum())
print("malformed examples:", sales.loc[malformed, 'txn_date'].unique()[:10])
print("empty-vs-unparseable overlap (should be 0):", (empty & d.isna()).sum(), "(empty => NaN)")

print("\n== orphans ==")
so = sales['store_id'] == '9999'; po = sales['product_id'] == '9999'
print("store_id==9999 rows:", so.sum(), "| product_id==9999 rows:", po.sum(), "| both:", (so&po).sum())

print("\n== qty outliers ==")
qty = num(sales['qty'])
big = qty >= 1000
print("qty>=1000 rows:", big.sum())
print("qty outlier value counts:", qty[big].value_counts().sort_index().to_dict())

print("\n== line_amount mismatch ==")
price = num(sales['unit_price']); amt = num(sales['line_amount'])
calc = (qty * price).round(2)
mis = (amt - calc).abs() > 0.01
print("mismatch rows:", mis.sum())
print("mismatch & qty-outlier overlap:", (mis & big).sum())
print("mismatch & NOT qty-outlier:", (mis & ~big).sum())
print("mismatch & missing-qty/price:", (mis & (qty.isna()|price.isna())).sum())
print("\nrows with mismatch and qty>=1000 sample:")
print(sales[mis & big][['txn_id','txn_date','store_id','product_id','qty','unit_price','line_amount']].head(8).to_string(index=False))

print("\n== duplicates ==")
dup_txn = sales['txn_id'].duplicated(keep=False)
groups = sales[dup_txn].groupby('txn_id')
print("txn_ids shared by >1 row:", groups.ngroups)
# how many are exact (identical) vs conflicting
exact = sales[dup_txn].groupby('txn_id').apply(lambda g: g.drop(columns=['txn_id']).duplicated().any())
def g_exact(g):
    return g.duplicated().sum()
identical_pairs = sales[dup_txn].groupby('txn_id')['txn_id'].transform('size')  # n per group
# count groups where all rows identical
def all_identical(g):
    return g.drop(columns=['txn_id']).nunique(dropna=False).eq(1).all()
res = sales[dup_txn].groupby('txn_id').apply(all_identical)
print("groups fully identical:", res.sum(), "| groups with conflicting content:", (~res).sum())
conflicting = sales[dup_txn][sales[dup_txn]['txn_id'].isin(res[res==False].index)]
print("\nconflicting duplicate groups (sample):")
print(conflicting.sort_values('txn_id').head(12).to_string(index=False))

print("\n== date gaps ==")
ds = pd.to_datetime(sales['txn_date'], errors='coerce').dropna()
days = sorted(ds.dt.date.unique())
print("distinct dates:", len(days), "from", days[0], "to", days[-1])
all_days = pd.date_range(days[0], days[-1]).date
missing_days = set(all_days) - set(days)
print("calendar days with NO transactions:", len(missing_days))
print("sample missing days:", sorted(missing_days)[:15])

print("\n== store/product/category reference totals ==")
print("products:", len(products), "| vendors:", len(vendors), "| stores:", len(stores), "| categories:", len(categories))
print("categories names:", categories['name'].tolist())