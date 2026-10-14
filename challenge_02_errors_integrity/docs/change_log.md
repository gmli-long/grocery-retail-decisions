# 变更日志（Change Log）

> 机器可读版本见 `data/clean/audit_log.csv`；本文是同一记录的易读形式。
> 修复流水线：`scripts/run_repair.py` → `src/helper_utils.py::repair()`。

| Step | 表 | 列 | 操作 | 行数 | 理由 |
|---|---|---|---|---|---|
| 0 | categories | name | 标准化标签 | 2 | 3 种命名约定（`Cat-One`/`category_2`/`Category_N`）并存，统一为 `Category_{id}` 以消除标签漂移 |
| 1 | sales | txn_id | 去重（保留最有效） | 50 | 50 个 txn_id 各出现两次（47 组完全相同 + 3 组冲突）；按「真实门店+真实商品+金额一致」评分保留每键最优成员 |
| 2 | sales | qty | 离群 ÷1000 | 29 | qty∈{1000..4000} 仅出现在金额已等于 qty×price 处，真实数量 = qty/1000 |
| 3 | sales | line_amount | 重算 = qty×price | 13 | 13 个金额被放大 100 倍（原始 14 个，1 个在去重中随冲突行移除）；金额是派生字段，从可信的 qty·price 重建 |
| 4 | sales | qty | 精确还原 | 56 | qty = line_amount / unit_price（原始 57 缺，1 行随重复组移除）；计数为整数 |
| 5 | sales | unit_price | 精确还原 | 56 | unit_price = line_amount / qty；全精度无猜测 |
| 6 | sales | txn_date | txn_id 分块前向填充 | 29 | 日期是 txn_id 的单调阶跃函数（每日连续块、60 天 0 反转），前向填充精确还原 |
| 7 | sales | store_id | 门店日循环序还原 | 13 | store_id=9999 为畸形键；每日门店 1→5 连续循环可唯一确定（原始 14，1 行随重复组移除；2 行在块边界用「后向块」决断） |
| 8 | sales | product_id | 频率加权采样补值 | 28 | product_id 与任何观测列均独立、但边际分布非均匀，无法确定性还原；种子化按 P(product) 重分配保持边际分布无偏（原始 29，1 行随重复组移除） |
| 9 | sales | line_amount | 规范化 = qty×price | 0 | 结果自洽化，全表不变量恒成立 |

## 净效应

- 行数：**2,859 → 2,809**（−50 重复行）
- 缺失值：txn_date / qty / unit_price 全部补齐（0 → 0 缺失）
- 引用完整性：0 孤儿、0 重复、0 越界
- 总额：$265,880 → $183,483（−31.0%，移除 $82,397 失真；即原始值相对真实值虚高 +44.9%）

## 可复现性

- 唯一随机来源：`product_id` 抽样，固定种子 `default_rng(42)`。
- 全部步骤确定性、无人工干预，`python scripts/run_repair.py` 一键重放。