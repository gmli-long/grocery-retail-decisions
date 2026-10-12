# 数据架构（Architecture）

## 1. 概览

挑战 02 复用挑战 01 建立的维度—事实结构，并追加一个「质量层」。数据流：

```
data/raw/   (5 CSV, 注入错误)         data/clean/  (5 CSV, 已修复)
    │                                        ▲
    │  src/helper_utils.py                    │
    │     audit()  -> repair() -> validate()  │
    └──────────►  scripts/run_repair.py ──────┘
                        │
                        ├─► data/clean/audit_log.csv   (变更日志)
                        └─► reports/figures/           (证据图)

src/evaluation.py  —— 独立完整性校验（可对 raw/clean 双向运行）
scripts/run_retest.py —— 基线重测（脏 vs 清洗）
```

## 2. 概念模型（5 表）

```mermaid
erDiagram
    VENDORS ||--o{ PRODUCTS : supplies
    CATEGORIES ||--o{ PRODUCTS : groups
    PRODUCTS ||--o{ SALES : sold-as
    STORES ||--o{ SALES : records

    VENDORS { int vendor_id PK; string name }
    CATEGORIES { int category_id PK; string name }
    PRODUCTS { int product_id PK; string sku; string name; int category_id FK; int vendor_id FK }
    STORES { int store_id PK; string name; string city }
    SALES { int txn_id PK; datetime txn_date; int store_id FK; int product_id FK; int qty; float unit_price; float line_amount }
```

- **维度**：vendors、categories、products（带 2 个 FK）、stores。
- **事实**：sales（交易级，`line_amount = qty × unit_price` 是核心派生不变量）。

## 3. 关键不变量（与质量层的关系）

| 不变量 | 审计用途 | 修复用途 |
|---|---|---|
| `txn_id` 唯一且稠密 `1..2809` | 检测重复键 | 去重、作为还原坐标轴 |
| `line_amount = qty × unit_price` | 检测金额不一致（43 行） | 精确还原缺失 qty/price、修正 ×100 |
| `txn_id → 日期` 单调阶跃（每日连续块） | 检测日期漂移/缺口 | 精确还原缺失日期（前向填充） |
| 每日门店 1→5 连续循环 | 检测孤儿 store | 精确还原 `store_id=9999` |
| `product_id ∈ 1..20` | 检测孤儿 product | 唯一无信号 → 频率加权采样补值 |

## 4. 清洗后 Schema 契约

`data/clean/sales.csv`：

| 列 | 类型 | 约束 |
|---|---|---|
| txn_id | int | 主键，唯一、稠密 `1..2809` |
| txn_date | `YYYY-MM-DD HH:MM:SS` | 非空、2024、随 txn_id 单调 |
| store_id | int | 外键 → stores，∈{1..5} |
| product_id | int | 外键 → products，∈{1..20} |
| qty | int | ∈ {1,2,3,4} |
| unit_price | float | > 0 |
| line_amount | float | = qty × unit_price |

## 5. 质量层组件

- `src/helper_utils.py` — `load_raw` / `audit` / `repair` / `validate` / `daily_store_revenue`（无副作用、确定性）。
- `src/evaluation.py` — 独立校验 CLI（18 项检查，raw 预期失败 / clean 预期通过）。
- 变更日志 — `data/clean/audit_log.csv` + `docs/change_log.md`（每步：表、列、操作、行数、理由）。