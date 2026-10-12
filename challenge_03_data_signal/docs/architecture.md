# 架构说明 — 挑战 03：数据 → 信号

## 数据流与依赖关系

```
data/raw/*.csv ──▶ src/helper_utils.py::build_panel ──▶ 日报表面板（21912 行）
      │                                                        │
      │                                         ┌──────────────┼───────────────┐
      ▼                                         ▼              ▼               ▼
  （干净，无注入错误）                     信号探索        无监督检测        预测
                                          run_eda.py     detect_anomalies   run_forecast.py
                                                │                            │
                                   ┌────────────┴───────┐         ┌──────────┴──────────┐
                                   ▼                    ▼         ▼                     ▼
                           signal_metrics.json  fig1–9  forecast_metrics.json  fig10–12
```

## 四个平面文件

| 文件 | 行数 | 关键列 | 角色 |
|---|---|---|---|
| `dates.csv` | 1,826 | `date, dow, dom, woy, month, quarter, year` | 日历维度（2018-01-01 ~ 2022-12-31，含闰日） |
| `categories.csv` | 4 | `category_id, name, seasonal_flag, perishability` | 品类维度 |
| `stores.csv` | 3 | `store_id, city, size, region` | 门店维度 |
| `sales.csv` | 21,912 | `date, store_id, category_id, sales_qty, sales_revenue` | 事实表（完整网格 4×3×1826，无缺日） |

> 完整性：`4 × 3 × 1826 = 21,912` 恰好等于 `sales` 行数——数据集是**无缺口的每日网格**（挑战 02 的信任在此兑现）。

## 衍生变量（确定性推导）

| 变量 | 公式 | 用途 |
|---|---|---|
| `unit_price` | `sales_revenue / sales_qty` | 价格信号、弹性分析 |
| `is_holiday` | 节假日日历命中 | 外部因子回归项 |
| `is_weekend` | `dow ∈ {5,6}` | 周度模式显式化 |
| `week_sin/cos`、`year_sin/cos` | 周期编码 | 备用特征（分析用） |
| `annual_sin/cos_k`（k=1,2） | 年度傅里叶 | SARIMAX 外生项 |

## 节假日日历（可复现，零外部依赖）

`helper_utils.us_holiday_calendar` 手写实现美国联邦节假日（OPM 顺延规则）+ 零售相关补充：

- 联邦节假：元旦、马丁·路德·金日、总统日、阵亡将士纪念日、独立日、劳动节、哥伦布日、退伍军人节、感恩节、圣诞节；2021 年起含六月节。
- 浮动规则：第 N 个周一/周四、最后一个周一，按 OPM「周六→周五、周日→周一」顺延。
- 零售补充：Black Friday（感恩节次日）、Christmas Eve。

因顺延可能使两个节日落在同一天（如圣诞日顺延到 12-24 = 圣诞夜），按日期去重合并标签。总计 61 个节假日（5 年）。

## 模型规格

### 无监督检测
- **周期检测**：去趋势后 FFT 周期图，取主导局部峰（抑制谐波），区间 2–400 天。
- **季节强度**：STL（周期=7，稳健）下 `1 − Var(resid)/Var(seasonal+resid)`。
- **异常/节假日检测**：STL 残差 Z-score，`|z|>3.5` 判异常；再与节假日日历交叉验证精确率。

### 预测（`src/forecast.py`）
- 时间切分：训练 2018–2021（1461 天），测试 2022（365 天全盲测）。
- 基准：persistence（昨日值）、seasonal-naive（上周同期）。
- `SARIMA(1,1,1)(1,0,1)[7]`：仅周度季节。
- `SARIMAX(1,1,1)(1,0,1)[7]` + 外生 `[is_holiday, annual_sin1/cos1, annual_sin2/cos2]`。
  - `d=1` 一次差分去除趋势；`P=1,Q=1,s=7` 捕捉周循环；年度起伏交给傅里叶外生项而非 `s=365`（后者计算代价高且易过拟合）。

## 可复现性契约

- 全流程确定性：SARIMA/SARIMAX 为数值优化，无随机种子；节假日日历手写；无远程下载。
- 一键重放：`python scripts/run_eda.py && python scripts/run_forecast.py`。
- 每个输出文件都能追溯到对应脚本与函数；指标以 `reports/*.json` 机器可读形式落地。

## 数据可追溯性（业务意义）

预测是「总→品类→门店」三层结构：总序列预测为「经营总盘子」提供落地口径，品类层揭示「谁的季节敏感度/预测难度高」（Bakery 最典型），门店层揭示「规模差异与节奏一致」。每一层共享同一套模型规格，保证口径一致、可逐级核对。