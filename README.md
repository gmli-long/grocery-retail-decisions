# 杂货零售 · 数据驱动决策（Grocery Retail — Data-Driven Decisions）

一套三阶段的端到端数据工程与数据科学项目，围绕 Greenway Grocers（合成教育数据，来源 Kaggle）展开，模拟一条真实企业数据链路：**从散乱难用的电子表格，到可信的数据底座，再到可解释的销售预测信号**。

三个阶段递进依赖，任何一步跳过都会让后续阶段成为空中楼阁：

| 阶段 | 主题 | 一句话本质 | 目录 |
|---|---|---|---|
| 01 | Spaghetti → Schema | 乱的表 → 有序的关系模型 | [`challenge_01_spaghetti_schema`](challenge_01_spaghetti_schema) |
| 02 | Errors → Integrity | 看似有序 → 真正可信 | [`challenge_02_errors_integrity`](challenge_02_errors_integrity) |
| 03 | Data → Signal | 干净的数据 → 可解释的预测 | [`challenge_03_data_signal`](challenge_03_data_signal) |

---

## 挑战 01 · 数据建模（Spaghetti → Schema）

把 4 个扁平 CSV（53,286 行流水明细，逐行冗余门店/供应商/商品属性，四季日期格式各异）逆向工程为 3NF 关系模型。

- 产出 11 张表（7 维 + 4 事实），PostgreSQL DDL + 索引，含 SQLite 回退
- 可靠 ETL：清洗、类型强制、键约束、引用完整性
- 行数对账与源文件精确一致（`REJECTED = 0`）
- 基线 RandomForest **MAPE 33.05%**（persistence 41.42%）

→ 详见 [`challenge_01_spaghetti_schema/README.md`](challenge_01_spaghetti_schema/README.md)

## 挑战 02 · 数据质量与完整性（Errors → Integrity）

对注入 9 类错误（缺失/重复/外键孤儿/离群/金额不一致）的结构化数据做审计、修复、验证。

- 方法论：**精确还原优先，统计补值兜底**（4/5 项由业务不变量反推，0 猜测）
- 完整性校验 **18/18 通过**，营收修正 −31.0%（移除 +44.9% 虚高）
- 脏数据基线 MAPE 由 303.7% 回落至 65.3%

→ 详见 [`challenge_02_errors_integrity/README.md`](challenge_02_errors_integrity/README.md)

## 挑战 03 · 时间序列信号（Data → Signal）

3 门店 × 4 品类 × 1826 天的干净日销售数据，提取周期/节假日信号并预测。

- FFT 周期图**无监督**识别 365.2 天（年）+ 7.0 天（周）双周期
- 节假日销售抬升 **+12.5%**，价格-数量相关 ≈ 0（描述性、非因果）
- 总序列 MAPE：朴素 20.5% → SARIMA 15.1% → **SARIMAX 10.5%**
- Bakery 品类在节假日+年度因子后 MAPE **78.3% → 30.4%**

→ 详见 [`challenge_03_data_signal/README.md`](challenge_03_data_signal/README.md)

---

## 贯穿主线的方法论

1. **可复现性**——每个挑战端到端一键重放、零人工干预；唯一随机来源显式固定。
2. **精确优先于猜测**——能反推的绝不盲填，每个选择给出理由与诊断。
3. **阶梯证明而非黑箱**——用「基准 → 中间态 → 终态」证明每个建模选择的增量价值。

## 验证

极简回归测试（仅标准库，零建模依赖）锁定跨三个阶段的关键不变量与措辞契约：

```bash
python -m unittest discover -s tests -v
```

## 技术栈

- 语言/工具：Python、SQL（PostgreSQL / SQLite）
- 数据：Pandas、NumPy、数据建模（3NF）、ETL
- 统计/建模：statsmodels（SARIMA/SARIMAX/STL）、SciPy（FFT）、scikit-learn（RandomForest）
- 可视化/文档：Matplotlib、ReportLab、python-pptx、Jupyter

> 注：数据为 Kaggle 合成教育数据，仅用于教学与技能展示，无真实商业敏感信息。