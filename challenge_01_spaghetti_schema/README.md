# 挑战 01 — 从数据混乱到分析清晰（Spaghetti → Schema）

将 Greenway Grocers 2024 年的一组**平面电子表格**，转化为一个**结构化、可查询、可复现的关系型数据底座**，并验证其分析与建模就绪度。

> 数据集为合成教育数据，来源：Kaggle `challenge-01-spaghetti-schema-2026`。

## 交付物清单（对照挑战要求）

| 挑战要求 | 本仓库位置 |
|---|---|
| 问题陈述与笔记本骨架 | [`docs/problem_statement.md`](docs/problem_statement.md)、[`notebooks/00_workflow_skeleton.ipynb`](notebooks/00_workflow_skeleton.ipynb) |
| 数据字典 | [`docs/data_dictionary.md`](docs/data_dictionary.md) |
| 实体关系图（ERD） | [`docs/erd.png`](docs/erd.png)、[`docs/architecture.md`](docs/architecture.md)（含 Mermaid） |
| 规范化模式 + DDL | [`sql/ddl.sql`](sql/ddl.sql)、[`sql/indexes.sql`](sql/indexes.sql) |
| ETL 流水线 | [`scripts/load_data.py`](scripts/load_data.py)、[`reports/etl/etl.log`](reports/etl/etl.log) |
| 探索性数据分析（EDA） | [`notebooks/01_eda.ipynb`](notebooks/01_eda.ipynb) + `reports/figures/*.png` |
| 基线模型 | [`notebooks/03_model_baseline.ipynb`](notebooks/03_model_baseline.ipynb) |
| 执行摘要 | [`reports/executive_summary.html`](reports/executive_summary.html)、[`reports/executive_summary.pdf`](reports/executive_summary.pdf) |
| 演示卡组 | [`slides/presentation_deck.pptx`](slides/presentation_deck.pptx)（7 页） |

## 目录结构

```
challenge_01_spaghetti_schema/
├── docs/            architecture.md · problem_statement.md · data_dictionary.md · erd.png
├── sql/             ddl.sql · indexes.sql
├── scripts/         load_data.py · eda.py · model_baseline.py · generate_erd.py
│                    generate_pdf.py · generate_deck.py · build_notebooks.py · profile_data*.py
├── notebooks/       00_workflow_skeleton.ipynb · 01_eda.ipynb · 03_model_baseline.ipynb
├── reports/         executive_summary.html · executive_summary.pdf
│                    figures/*.png · etl/etl.log · etl/rejected_rows.csv
├── slides/          presentation_deck.pptx
└── data/            challenge_01.sqlite   (本地验证产物，非源数据)
```

## 运行方式

```powershell
# 1) 重建数据库：清洗 → 类型强制 → 校验 → 加载
python scripts/load_data.py --target sqlite            # SQLite（本地验证）
python scripts/load_data.py --target postgres          # PostgreSQL（需 DATABASE_URL）

# 2) EDA（生成 figures/*.png 与洞察）
python scripts/eda.py

# 3) 基线模型（MAE/RMSE/MAPE + 预测图）
python scripts/model_baseline.py

# 4) 重新生成 ERD / PDF / 卡组 / notebooks（可选）
python scripts/generate_erd.py
python scripts/generate_pdf.py
python scripts/generate_deck.py
python scripts/build_notebooks.py
```

`load_data.py` 面向 PostgreSQL（挑战指定的数据库），同时提供 **SQLite 回退** 以便在无 Postgres 的环境下直接复现全链路。两种后端的规范化模型完全一致。

## 关键结果

- **行数对账**：products=60 · promotions=530 · stores=3 · cashiers=8 · receipts=13,259 · line_items=53,286 · inventory_snapshots=2,160 —— 与源文件 `readme.txt` 精确一致；`REJECTED rows = 0`。
- **EDA**：Grocery 占营收 34%（$174k）；三店体量均衡；BOGO50 提量效果显著（行均数量 1.29→2.16）。
- **基线模型**（单店每日销售，训练 1–10 月 / 测试 11–12 月）：

| 模型 | MAE ($) | RMSE ($) | MAPE (%) |
|---|---|---|---|
| persistence | 176.1 | 224.1 | 41.42 |
| weekday_naive | 197.6 | 241.4 | 48.52 |
| **random_forest** | **135.8** | **170.6** | **33.05** |

## 依赖

Python 3.10 + `pandas`、`numpy`、`matplotlib`、`seaborn`、`scikit-learn`、`reportlab`、`python-pptx`；PostgreSQL 后端需 `psycopg2`（可选）。