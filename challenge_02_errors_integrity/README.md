# 挑战 02 — 错误 → 诚信（Errors → Integrity）

把「结构化但混乱」的杂货零售数据集，审计、修复、验证为**可审计、可复现、AI 就绪**的可信底座。

- **9 类注入错误** 全量枚举；
- **4/5 项精确还原**（qty / unit_price / txn_date / store_id 从业务不变量反推，0 猜测），仅 product_id 无信号做种子化比例抽样；
- **18/18 完整性校验通过**；
- 清洗移除 **$82,397** 营收虚高（原始值相对真实值 +44.9%），基线误差降 **3–5 倍**。

## 一键运行（无需人工干预）

```powershell
cd challenge_02_errors_integrity

python scripts/run_repair.py      # 审计 -> 修复 -> 验证 -> 落盘 data/clean + 图表
python scripts/run_retest.py      # 基线重测（脏 vs 清洗）
python scripts/build_notebooks.py # 重建两份 notebook（含真实输出）
python scripts/generate_pdf.py    # reports/executive_summary.pdf
python scripts/generate_deck.py   # slides/presentation_deck.pptx

python src/evaluation.py --data data/clean    # 完整性校验（exit 0）
python src/evaluation.py --data data/raw      # 完整性校验（预期失败，exit 1）
```

依赖：`pandas numpy scikit-learn matplotlib reportlab python-pptx`（无 jupyter 依赖即可生成含输出的 notebook）。

## 目录结构

```
challenge_02_errors_integrity/
├── data/
│   ├── raw/                  # 5 张原始 CSV（含注入错误）+ readme
│   └── clean/                # 5 张清洗后 CSV + audit_log.csv
├── docs/
│   ├── problem_statement.md  # 业务背景与质量目标
│   ├── architecture.md       # 数据架构 + 质量层 + 不变量契约
│   └── change_log.md         # 逐条变更（表/列/操作/行数/理由）
├── notebooks/
│   ├── 02_data_quality.ipynb # 审计 → 修复 → 验证（含执行输出）
│   └── 02_model_retest.ipynb # 基线重测（脏 vs 清洗）
├── reports/
│   ├── data_quality.md       # 数据质量报告（主交付物）
│   ├── executive_summary.pdf # 执行摘要（含图表）
│   ├── metrics.json          # 全部审计计数 + 校验结果
│   ├── retest_metrics.json   # 重测指标
│   └── figures/              # fig1–fig5 证据图
├── src/
│   ├── helper_utils.py       # 审计/修复/验证核心函数（确定性）
│   └── evaluation.py         # 完整性校验 CLI（18 项检查）
├── scripts/                  # run_repair / run_retest / build_notebooks / generate_pdf / generate_deck
└── slides/presentation_deck.pptx
```

## 交付物清单（对照验收标准）

| 交付物 | 路径 | 状态 |
|---|---|---|
| 问题陈述与笔记本骨架 | `docs/problem_statement.md` + `02_data_quality.ipynb` | ✅ |
| 数据质量报告 | `reports/data_quality.md` | ✅ |
| 审计与维修笔记本 | `notebooks/02_data_quality.ipynb` | ✅ |
| 验证脚本 | `src/evaluation.py` | ✅ |
| 基线重测笔记本 | `notebooks/02_model_retest.ipynb` | ✅ |
| 架构 + 变更日志 | `docs/architecture.md`、`docs/change_log.md` | ✅ |
| 执行摘要 + 演示卡组 | `reports/executive_summary.pdf`、`slides/presentation_deck.pptx` | ✅ |

## 验收结果

- ✅ 所有注入问题被发现并**修复或明确说明**（product_id 明确标注为无信号、抽样补值）；
- ✅ 每个补值步骤配有**理由与诊断**（见 `change_log.md` 与 notebook）；
- ✅ 清洗后重新训练基线，**无异常指标跳跃**（误差降 3–5 倍，回落到噪声地板）；
- ✅ 全部笔记本与脚本**端到端运行、零人工干预**。

## 关键数字

| 指标 | 原始 | 清洗后 |
|---|---:|---:|
| sales 行数 | 2,859 | 2,809 |
| 总营收 | $265,880 | **$183,483** (−31.0%) |
| 完整性校验 | — | 18/18 PASS |
| 基线 MAPE（RF） | 303.7% | 65.3% |