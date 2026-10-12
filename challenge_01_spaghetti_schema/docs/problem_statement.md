# 挑战 01 — 问题陈述（Problem Statement）

## 业务背景

Greenway Grocers（Greenway 杂货连锁）在 2024 年使用一组**扁平电子表格**运营其 3 家门店的零售业务。这些表格由一线运营系统直接导出，以便于「人肉翻看」而非「分析查询」为优化目标：

| 来源文件 | 含义 | 典型问题 |
|---|---|---|
| `products_2024.csv` | 商品主档（60 个 SKU） | 供应商、部门、尺寸等描述性属性与商品平铺 |
| `promotions_2024.csv` | 每周促销（530 条） | 重复携带商品名称/部门/品牌 |
| `inventory_snapshots_2024.csv` | 月度库存快照（2,160 条） | 重复携带门店与商品的全部属性 |
| `sales_2024_q1..q4.csv` | 流水明细（53,286 行） | **每一行**都重复门店、供应商、商品、品牌等属性；四个季度的日期时间格式各不相同 |

这些文件能回答「昨天某店卖了什么」，却难以回答业务真正关心的问题：各部门的周销售额、促销的真实增量（lift）、会员贡献度、门店对比、单店每日销售的预测基线。

## 数据目标

把「散乱的表格」改造成**一个结构化、可查询、可复现的关系型数据底座**，成为后续所有阶段（Challenge 02 数据质量与错误、预测、ROI 建模）的骨干。

具体而言，本挑战要交付：

1. **逆向工程数据模型** —— 识别实体（门店、商品、供应商、部门、收银员、促销、小票、流水明细、库存快照），用概念性 ERD 定义它们的关系（见 `docs/architecture.md` / `docs/erd.png`）。
2. **规范化以保证可扩展** —— 按 3NF 实现 PostgreSQL 模式，同时保留分析灵活性（`sql/ddl.sql`）。
3. **可靠的 ETL** —— 可重复的加载脚本，完成清洗、类型强制、键约束与引用完整性（`scripts/load_data.py`）。
4. **分析就绪证明** —— 用规范化后的 schema 支撑有意义的业务查询（`notebooks/01_eda.ipynb`）与一个简单的每日销售预测基线（`notebooks/03_model_baseline.ipynb`）。
5. **记录逻辑** —— 每个建模选择都给出清晰的数据字典、模式图与简明理由。

## 成功标准

本挑战「通过」的判据（可验证）：

| # | 标准 | 验证方式 |
|---|---|---|
| S1 | 每张事实表/维度表加载后**行数与源文件精确一致** | ETL 日志：products=60、promotions=530、inventory_snapshots=2,160、receipts=13,259、line_items=53,286 |
| S2 | **无引用完整性违规**（0 行孤儿或外键失败） | ETL 日志 `REJECTED rows: 0` + 数据库 FK 约束 |
| S3 | **四季度异构时间格式被统一**为单一 `TIMESTAMP` | ETL 类型强制 + 数据字典 |
| S4 | schema 能**直接支撑业务查询**（部门×周、促销 lift、会员占比） | EDA 中的 SQL join 查询 |
| S5 | 基线模型报告 ≥1 个指标，且**优于朴素基线** | MAE/RMSE/MAPE，RF vs 持久化/周季节基线 |

## 关键业务规则（逆向工程得到的领域知识）

- 定价：`regular_price` 与 `unit_cost` 是**商品级基线**；`unit_price_effective` 反映促销（`PCT_OFF`/`LOYALTY_PCT` 打折、`BOGO50` 买一第二件半价）；`line_subtotal = unit_price_effective × quantity`。
- 税费：仅 **Wellness** 品类按 **10.1%** 计 `tax_amount`，其余为零。
- 促销规则：`LOYALTY_PCT` 面向会员、`PCT_OFF` 面向全场、`BOGO50` 以「每两件中一件半价」实现（数量为奇数时仍成立）。
- 每张票据（receipt）内的 `store_id / cashier_name / tender_type / customer_segment / sale_datetime` 恒定，属于**票头**而非行级属性。
- `weekend_flag` 与 `sale_datetime` 100% 一致，是**可推导的冗余列**。