🧹 Challenge 02 – Errors → Integrity

Dataset README
==============

This dataset accompanies **Challenge 02 – Errors → Integrity** in the *Grocery Retail – Driven by Data* series.
It represents a structured but imperfect grocery database — a realistic mix of missing values, duplicates, inconsistent codes, and timestamp drift — for practicing systematic data auditing and repair.

📁 Files Included
----------------
| File | Description |
|------|--------------|
| `products.csv` | Product master list with IDs, names, categories, and supplier/vendor links. Contains missing or inconsistent codes. |
| `vendors.csv` | Vendor reference table; some duplicates and mismatched foreign keys appear here. |
| `stores.csv` | Store metadata including region, timezone, and size class. Several entries exhibit time-zone drift or malformed IDs. |
| `sales.csv` | Transaction-level sales data linking product, store, date, and quantity. Includes missing totals, date gaps, and duplicates for testing validation logic. |
| `categories.csv` | Product-category hierarchy and grouping definitions; some orphaned or redundant entries may exist. |

🧾 Objective
------------
Your task is to **detect, repair, and validate** the data to produce a trustworthy foundation for analytics and modeling.

Participants should:
- Audit for completeness, duplicates, drift, and out-of-range values.
- Apply principled repairs or imputations while preserving data meaning.
- Validate that cleaned data remain consistent across tables.
- Document every change transparently.

🧰 Recommended Workflow
-----------------------
1. **Audit Setup:** Load all CSVs and generate summary statistics / missingness maps.  
2. **Error Detection:** Identify duplicates, mismatched keys, and timestamp inconsistencies.  
3. **Repair & Imputation:** Use mean/median/kNN/time-based methods and categorical standardization.  
4. **Validation:** Confirm referential integrity and statistical stability (no spurious jumps).  
5. **Documentation:** Record all fixes in `reports/data_quality.md` or similar log.

🧱 Expected Outputs
-------------------
- `notebooks/02_data_quality.ipynb` — audit + repair notebook  
- `reports/data_quality.md` — summary of issues and fixes  
- `src/evaluation.py` — integrity-check script  
- *(Optional)* `02_model_retest.ipynb` for comparing pre- and post-cleaning model performance

⚖️ License
----------
**CC BY-NC-SA 4.0** — You may share and adapt the dataset for non-commercial educational or research purposes with proper attribution.
