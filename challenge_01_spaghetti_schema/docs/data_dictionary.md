# 数据字典（Data Dictionary）

覆盖四个源文件中的所有列。四张销售表（Q1–Q4）**字段结构完全相同**，仅在 `sale_datetime` 的字符串格式上不同（见下方「格式不一致」）。最后一列 `目标表` 标明该列在规范化后落入哪张表，`—` 表示因冗余/可推导而被 ETL 丢弃。

## 1. products_2024.csv（商品主档，60 行）

| 列 | 数据类型 | 有效范围 / 取值 | 示例 | 业务含义 | 目标表 |
|---|---|---|---|---|---|
| product_upc | VARCHAR(12) | 12 位数字，全表唯一 | `433218196001` | 商品统一编码（自然主键） | products |
| product_name | TEXT | 非空自由文本 | `Rainshadow Produce Apples` | 商品显示名 | products |
| brand | TEXT | 21 个品牌 | `Sun Valley` | 品牌（1:N 商品） | brands |
| department_name | TEXT | 8 个部门 | `Produce`, `Grocery` | 所属部门 | departments |
| category_name | TEXT | 60 个叶子类目 | `Apples`, `Olive Oil` | 最细粒度品类 | categories |
| size | TEXT | `1 lb`…`120 ct`（19 种） | `16 oz` | 包装规格标签 | products |
| unit | TEXT | lb / oz / gal / qt / ct / each | `oz` | 计量单位 | products |
| vendor_name | TEXT | 9 个供应商 | `Evergreen Organics` | 供货商 | vendors |
| vendor_phone | TEXT | `206-555-XXXX` | `206-555-0110` | 供应商电话（每个 vendor 唯一） | vendors |
| regular_price | NUMERIC(10,2) | 0.92 – 35.34 | `3.11` | 基准零售价（$） | products |
| unit_cost | NUMERIC(10,2) | 0.69 – 24.51 | `2.31` | 基准单位成本（$） | products |
| pack_size | SMALLINT | 1 / 2 / 4 / 6 | `1` | 每包内件数 | products |

## 2. promotions_2024.csv（促销，530 行）

| 列 | 数据类型 | 有效范围 / 取值 | 示例 | 业务含义 | 目标表 |
|---|---|---|---|---|---|
| promo_id | VARCHAR(9) | `PR` + 7 位数字，唯一 | `PR0011832` | 促销主键 | promotions |
| product_upc | VARCHAR(12) | 均存在于 products | `471349361832` | 促销作用的商品 | promotions(FK) |
| promo_type | TEXT | PCT_OFF / LOYALTY_PCT / BOGO50 | `PCT_OFF` | 促销机制 | promotions |
| discount_percent | NUMERIC(5,2) | 5 / 10 / 15 / 20 / 25 / 30 / 50 | `15` | 折扣百分比 | promotions |
| start_date | DATE | 2024-01-01 – 2024-12-31 | `2024-01-01` | 促销开始（每周一） | promotions |
| end_date | DATE | ≥ start_date | `2024-01-07` | 促销结束（每周日） | promotions |
| product_name | TEXT | 与 products 完全一致 | `Meadow Meats Salmon Fillet` | 冗余的商品名 | —（丢弃） |
| department_name | TEXT | 与 products 一致 | `Meat/Seafood` | 冗余的部门 | —（丢弃） |
| brand | TEXT | 与 products 一致 | `Meadow Meats` | 冗余的品牌 | —（丢弃） |

## 3. inventory_snapshots_2024.csv（月度库存，2,160 行）

| 列 | 数据类型 | 有效范围 / 取值 | 示例 | 业务含义 | 目标表 |
|---|---|---|---|---|---|
| snapshot_date | DATE | 每月 1 日，12 个快照 | `2024-01-01` | 快照日期 | inventory_snapshots |
| store_id | SMALLINT | 101 / 102 / 103 | `101` | 门店 | stores / inventory |
| store_name | TEXT | 3 家门店 | `Greenway - Northside` | 门店名（冗余） | stores |
| store_address | TEXT | — | `1201 Maple Ave` | 门店地址（冗余） | stores |
| store_city | TEXT | Everton | `Everton` | 城市（冗余） | stores |
| store_state | CHAR(2) | WA | `WA` | 州（冗余） | stores |
| store_zip | TEXT | 98111 / 98112 / 98113 | `98111` | 邮编（冗余） | stores |
| product_upc | VARCHAR(12) | 60 个商品 | `433218196001` | 商品 | inventory(FK) |
| product_name | TEXT | 冗余 | `Rainshadow Produce Apples` | — | —（丢弃） |
| department_name | TEXT | 冗余 | `Produce` | — | —（丢弃） |
| on_hand_qty | INT | 0 – 127（0=缺货） | `35` | 期末在手数量 | inventory_snapshots |
| unit_cost | NUMERIC(10,2) | 恒等于 products.unit_cost | `2.31` | **冗余**单位成本 | —（丢弃，可推导） |
| inventory_cost_value | NUMERIC(10,2) | = on_hand × unit_cost | `80.85` | **冗余**库存金额 | —（丢弃，可推导） |

## 4. sales_2024_q1..q4.csv（流水明细，共 53,286 行）

> 每个季度文件的 `sale_datetime` 字符串格式不同，见下表底部。

| 列 | 数据类型 | 有效范围 / 取值 | 示例 | 业务含义 | 目标表 |
|---|---|---|---|---|---|
| receipt_id | VARCHAR | `{store}-{YYYYMMDD}-{seq}` 唯一 | `101-20240101-0001` | 小票主键（票头） | receipts |
| line_number | SMALLINT | 1 – 13，票内连续 | `1` | 票内行号 | line_items |
| sale_datetime | TIMESTAMP | 2024-01-01 – 2024-12-31 | `2024-01-01 14:20` | 本地门店成交时间 | receipts |
| store_id | SMALLINT | 101 / 102 / 103 | `101` | 门店（票级恒定） | receipts(FK) |
| store_name | TEXT | 冗余 | `Greenway - Northside` | — | stores |
| store_address | TEXT | 冗余 | `1201 Maple Ave` | — | stores |
| store_city | TEXT | 冗余 | `Everton` | — | stores |
| store_state | CHAR(2) | 冗余 | `WA` | — | stores |
| store_zip | TEXT | 冗余 | `98111` | — | stores |
| cashier_name | TEXT | 8 名收银员 | `Quinn` | 收银员（票级恒定） | cashiers |
| tender_type | TEXT | Cash / Credit / SNAP | `SNAP` | 支付方式 | receipts |
| customer_segment | TEXT | Member / Non-Member | `Member` | 会员/非会员 | receipts |
| product_upc | VARCHAR(12) | 60 个商品 | `566701065133` | 商品 | line_items(FK) |
| product_name | TEXT | 冗余 | `Cascadia Creamery Cheddar Cheese` | — | products |
| brand | TEXT | 冗余 | `Cascadia Creamery` | — | brands |
| department_name | TEXT | 冗余 | `Dairy` | — | departments |
| category_name | TEXT | 冗余 | `Cheddar Cheese` | — | categories |
| size | TEXT | 冗余 | `8 oz` | — | products |
| unit | TEXT | 冗余 | `oz` | — | products |
| vendor_name | TEXT | 冗余 | `Ocean Crest Seafood` | — | vendors |
| vendor_phone | TEXT | 冗余 | `206-555-0116` | — | vendors |
| pack_size | SMALLINT | 冗余 | `1` | — | products |
| regular_price | NUMERIC(10,2) | 冗余（=products） | `5.34` | 基准零售价 | products |
| unit_cost | NUMERIC(10,2) | 冗余（=products） | `3.24` | 基准成本 | products |
| quantity | SMALLINT | 1 – 3 | `1` | 购买数量 | line_items |
| promo_type | TEXT | 空串 / PCT_OFF / LOYALTY_PCT / BOGO50 | `LOYALTY_PCT` | 应用的促销类型 | promotions |
| promo_id | TEXT | 空串或存在于 promotions | `PR0011647` | 应用的促销（可空） | line_items(FK,NULL) |
| unit_price_effective | NUMERIC(10,2) | = price × (1−disc) 或 BOGO 半价取整 | `1.09` | 实际成交单价 | line_items |
| line_subtotal | NUMERIC(10,2) | = unit_price_effective × quantity | `1.09` | 本行小计 | line_items |
| tax_amount | NUMERIC(10,2) | 0 或 Wellness 的 10.1% | `0.0` | 本行税额 | line_items |
| weekend_flag | BOOL | True / False | `False` | 是否周末（**可推导**） | —（丢弃） |

### 日期时间格式不一致（重要）

| 季度 | 原始格式 | 示例 |
|---|---|---|
| Q1 | `MM/DD/YYYY HH:MM` | `01/01/2024 14:20` |
| Q2 | `YYYY-MM-DD HH:MM` | `2024-04-01 11:23` |
| Q3 | `DD-Mon-YYYY HH:MM` | `01-Jul-2024 08:45` |
| Q4 | `MM/DD/YY hh:MM AM/PM` | `10/01/24 12:25 PM` |

ETL 在读取每个季度文件时按各自的格式解析，统一转换为 `TIMESTAMP`。