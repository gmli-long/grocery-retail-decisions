# 挑战 03 — 数据 → 信号（Data → Signal）

把挑战 01/02 建立起来的**可信数据**，转化为**可解释、可复现、业务意识**的预测信号。

- **无监督发现**：FFT 周期图自动识别 **7 天（周）** + **~365 天（年）** 双主导周期；
- **外部因子**：节假日销售抬升 **+12.5%**，价格-数量相关（描述性、非因果）≈ 0（需求由日历驱动）；
- **可解释预测**：总序列 MAPE 从朴素 20.5% → SARIMA 15.1% → **SARIMAX 10.5%**；
- **教科书案例**：Bakery 品类在加入节假日+年度因子后 MAPE **78% → 30%**。

## 一键运行（无需人工干预）

```powershell
cd challenge_03_data_signal

python scripts/run_eda.py        # 信号探索 -> fig1–9 + reports/signal_metrics.json
python scripts/run_forecast.py   # SARIMA/SARIMAX 预测 -> fig10–12 + reports/forecast_metrics.json
python scripts/build_notebooks.py# 重建两份 notebook（含真实输出）
python scripts/generate_pdf.py   # reports/executive_summary.pdf
python scripts/generate_deck.py  # slides/presentation_deck.pptx
```

依赖：`pandas numpy scipy matplotlib statsmodels reportlab python-pptx`（无 jupyter 依赖即可生成含输出的 notebook）。

## 目录结构

```
challenge_03_data_signal/
├── data/raw/                 # 4 张干净 CSV（dates/categories/stores/sales）
├── docs/
│   ├── problem_statement.md  # 业务背景与信号目标
│   └── architecture.md       # 数据流、模型规格、可复现性契约
├── notebooks/
│   ├── 03_data_signal.ipynb  # 信号探索（周期/季节/节假日/异常检测）
│   └── 03_forecast.ipynb     # 预测（基准→SARIMA→SARIMAX）
├── reports/
│   ├── data_signal_report.md # 主报告
│   ├── executive_summary.pdf # 执行摘要（含图表）
│   ├── signal_metrics.json   # 信号指标（周期/季节强度/节假日/异常）
│   ├── forecast_metrics.json # 预测指标（总/品类/门店）
│   └── figures/              # fig1–fig12 证据图
├── src/
│   ├── helper_utils.py       # 数据加载/节假日日历/信号度量/STL/异常检测
│   └── forecast.py           # 基准 + SARIMA/SARIMAX + 评估
├── scripts/                  # run_eda / run_forecast / build_notebooks / generate_pdf / generate_deck
└── slides/presentation_deck.pptx
```

## 关键数字

| 指标 | 数值 |
|---|---:|
| 数据规模 | 3 门店 × 4 品类 × 1826 天 = 21,912 条 |
| 主导周期（无监督） | 365.2 天、7.0 天 |
| 节假日销售抬升 | +12.5% |
| 总序列 MAPE（朴素→SARIMA→SARIMAX） | 20.5% → 15.1% → **10.5%** |
| Bakery 品类 MAPE（SARIMA→SARIMAX） | 78.3% → **30.4%** |
| 无监督异常命中节假日 | 12 / 18（精确率 66.7%） |

## 可复现性

- 可复现（同一环境）：SARIMA/SARIMAX 为数值优化、无显式随机种子，跨平台可能有浮点级微差；节假日日历手写、零远程依赖。
- 每个输出文件可追溯到对应脚本与函数；指标以 `reports/*.json` 机器可读形式落地。
- 所有笔记本与脚本**端到端运行、零人工干预**。