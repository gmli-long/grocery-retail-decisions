"""Challenge 02 — determine structure for repair decisions."""
import pandas as pd
import numpy as np

D = r"C:\Users\21597\.cache\kagglehub\competitions\challenge-02-errors-integrity-2026\challenge_02_data"
def load(n): return pd.read_csv(f"{D}\\{n}", dtype=str, keep_default_na=False)
def num(x): return pd.to_numeric(x, errors='coerce')

products = load("products.csv")
sales = load("sales.csv")

print("== unit_price structure by product ==")
up = num(sales['unit_price'])
sales2 = sales.copy(); sales2['up'] = up
g = sales2.groupby('product_id')['up'].agg(['count','mean','std'])
print(g.round(2).to_string())

print("\n== qty distribution (clean only 1..4) ==")
qty = num(sales['qty'])
print(qty[(qty>=1)&(qty<=4)].value_counts().sort_index().to_dict(),
      "| median:", qty[(qty>=1)&(qty<=4)].median())

print("\n== missing-field overlap ==")
m_date = sales['txn_date']==''; m_qty = qty.isna(); m_price = up.isna()
print("missing date:", m_date.sum(), "| missing qty:", m_qty.sum(), "| missing price:", m_price.sum())
print("date&qty both missing:", (m_date&m_qty).sum())
print("date&price both missing:", (m_date&m_price).sum())
print("qty&price both missing:", (m_qty&m_price).sum())
print("all three missing:", (m_date&m_qty&m_price).sum())

print("\n== 14 non-outlier line_amount mismatches: ratio ==")
amt = num(sales['line_amount']); price = up
calc = (qty*price).round(2)
mis = (amt-calc).abs()>0.01
big = qty>=1000
sub = sales[mis & ~big].copy()
sub['qty']=num(sub['qty']); sub['price']=num(sub['unit_price']); sub['amt']=num(sub['line_amount'])
sub['true'] = (sub['qty']*sub['price']).round(2)
sub['ratio'] = sub['amt']/sub['true']
print("count:", len(sub))
print(sub[['txn_id','qty','price','amt','true','ratio']].round(3).to_string(index=False))

print("\n== txn_id monotonic vs date? (correlation of order) ==")
s = sales.copy()
s['_d'] = pd.to_datetime(s['txn_date'], errors='coerce')
s['tid'] = num(s['txn_id'])
s2 = s.dropna(subset=['_d','tid']).sort_values('tid')
mono = (s2['_d'].diff().dt.total_seconds().fillna(0) >= -1).all()
print("date non-decreasing as txn_id increases:", mono)
print("txn_id range:", s2['tid'].min(), "-", s2['tid'].max(), "| date range:", s2['_d'].min(), "-", s2['_d'].max())
# check: is date perfectly tied to txn_id (each txn_id maps to one date)? 
n_tid = s2.groupby('tid')['_d'].nunique()
print("txn_ids mapping to >1 date:", (n_tid>1).sum(), "| total txn_ids:", len(n_tid))