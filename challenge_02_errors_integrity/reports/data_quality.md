# 数据质量报告 — 挑战 02 · 错误 → 诚信

> **目标**：把「结构化但混乱」的零售数据集转化为可审计、可复现、AI 就绪的可信数据底座。
> 全文通过 `notebooks/02_data_quality.ipynb` 与 `src/evaluation.py` 端到端复现。

## 1. 概览

| 指标 | 原始 | 清洗后 |
|---|---:|---:|
| sales 行数 | 2,859 | 2,809 |
| 检测到的问题类别 | 9 | 0（18/18 校验通过） |
| 总营收（Σ line_amount） | $265,880 | **$183,483** |
| 营收虚高 | — | **+44.9%（$82,397 失真）** |

原始营收被金额 ×100 错误与重复计费抬高了近一半；清洗后所有注入错误被修复或明确说明，且**没有扭曲关键分布**。

## 2. 审计发现（9 类错误）

| # | 类别 | 表·列 | 计数 | 形态 |
|---|---|---|---:|---|
| 1 | 缺失值 | sales.txn_date | 29 | 空字符串，非空日期全部可解析（0 漂移） |
| 2 | 缺失值 | sales.qty | 57 | 空值 |
| 3 | 缺失值 | sales.unit_price | 56 | 空值 |
| 4 | 重复键 | sales.txn_id | 50 组 / 100 行 | 47 组完全相同、3 组内容冲突 |
| 5 | 外键孤儿 | sales.store_id | 14 | `9999` 不在 stores 表 |
| 6 | 外键孤儿 | sales.product_id | 29 | `9999` 不在 products 表 |
| 7 | 数量离群 | sales.qty | 29 | {1000, 2000, 3000, 4000}，金额却=真实 qty×price |
| 8 | 金额不一致 | sales.line_amount | 43 | ≠ qty×price（其中 14 行为 ×100、29 行为数量离群） |
| 9 | 类别漂移 | categories.name | 2 | `Cat-One`/`category_2` 与 `Category_N` 混用 |

**未发现的问题**（已核查并排除）：负数金额/单价为 0（无）、日期格式漂移（统一 `YYYY-MM-DD HH:MM:SS`）、日历缺口（60 天连续）、products/vendors/stores 主键重复（无）。README 提到的「时区漂移」列在真实 schema 中不存在（stores 仅 id/name/city）。

## 3. 修复方法与理由

修复遵循一条硬原则：**能精确还原就绝不统计猜测**。

| 步骤 | 修复 | 方法 | 理由 / 诊断 |
|---|---|---|---|
| 0 | 类别命名 | 标准化为 `Category_{id}` | 3 种命名约定并存属标注漂移，统一后可按键命名 join |
| 1 | txn_id 去重 | 保留「最有效」成员 | 交易键唯一；3 组冲突以「真实门店+真实商品+金额一致」评分择优（含 txn 407/1293/734） |
| 2 | qty 离群 | ÷1000 | 数量被放大 1000 倍而金额正确 → 真实数量 = qty/1000 |
| 3 | line_amount ×100 | 重算为 qty×price | 金额是派生字段，应由（可信的）qty·price 重建（14+1 行，去重后 13） |
| 4 | 缺失 qty | = line_amount / unit_price | **精确还原**；qty 为整数且 ∈[1,4]，无需统计插补 |
| 5 | 缺失 unit_price | = line_amount / qty | **精确还原**；全精度，无猜测 |
| 6 | 缺失 txn_date | txn_id 分块前向填充 | **时间感知精确还原**：日期是 txn_id 的单调阶跃函数（每段连续，60 天 0 反转） |
| 7 | store_id=9999 | 门店日循环序 | **结构感知精确还原**：每日门店按 1→5 连续循环，13 行中 11 行唯一确定、2 行为块边界用后向块 |
| 8 | product_id=9999 | 种子化按经验频数采样 | **唯一无信号列**：与 qty/price/store/date 均独立、但边际分布非均匀，故按 P(product) 重分配以保持边际分布无偏 |
| 9 | line_amount | 规范化 = qty×price | 保证全表自洽（不变量恒成立） |

**为什么用比例抽样而非众数/丢弃处理 product_id**：众数会制造单商品尖峰（扭曲分布），丢弃会损失 28 行（≈1% 交易）；种子化比例抽样（`default_rng(42)`）既不改变边际分布、又保留全部交易、且逐字节可复现。

## 4. 前后对比（诊断）

- **缺失画像**：txn_date / qty / unit_price 三列缺失，`line_amount` 无缺失——这是能精确反推 qty 与 price 的前提（见 `fig1_missing_values.png`）。
- **数量分布**：原始在 1000–4000 出现 29 个尖峰，清洗后仅剩 1–4（见 `fig2_qty_spikes.png`）。
- **金额一致性**：`log10(line_amount/(qty·price))` 直方图暴露两簇异常（ratio≈100 与 ratio≈10⁻³），正常行 ratio=1（见 `fig3_amount_ratio.png`）。
- **每日营收**：清洗把虚高 43.6% 的日曲线拉回真实水位，且**无任何一日的曲线形状被扭曲**（见 `fig4_daily_revenue.png`）。

## 5. 验证结果

`src/evaluation.py`（对 `data/clean`）运行 **18 项引用完整性 / 越界 / 一致性 / 模式检查，全部 PASS**：

- 主键唯一（5 表）、txn_id 唯一且稠密 `1..2809`
- store_id / product_id / category_id / vendor_id 引用完整（0 孤儿）
- qty ∈ {1,2,3,4} 且为整数、unit_price > 0
- `line_amount == qty × unit_price`（max 偏差 < 1e-6）
- 日期全部可解析、落在 2024、随 txn_id 单调、无日历缺口

反方向（对 `data/raw` 运行同一脚本）会**失败**，用于证明检查有效、清洗必要。

## 6. 可复现性

```bash
python scripts/run_repair.py    # 审计 -> 修复 -> 验证 -> 落盘 data/clean + 图表
python scripts/run_retest.py    # 基线重测（脏 vs 清洗）
python src/evaluation.py --data data/clean   # 完整性校验（exit 0）
python src/evaluation.py --data data/raw     # 完整性校验（预期失败）
```

- 随机性唯一来源是 `product_id` 抽样，固定种子 `42`，结果逐字节可复现。
- 全部变更记录在 `data/clean/audit_log.csv` 与 `docs/change_log.md`。

## 7. 结论

挑战 02 把「有序」升级为「可信」：9 类注入错误全被检测，其中 **4 项（qty/unit_price/txn_date/store_id）精确还原、1 项（product_id）原则性补值、其余为去重/标准化**；18/18 校验通过、基线误差从 ~250–300% MAPE 回落到 ~55–80%，证明清洗**消除失真而非制造跳跃**，为挑战 03（数据→信号）铺好可信基础。