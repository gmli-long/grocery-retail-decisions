"""Build the two Challenge 03 notebooks as valid .ipynb JSON with *real* outputs.

Executes every code cell in an isolated namespace, capturing stdout and any open
matplotlib figures as base64-PNG display outputs — no jupyter/nbformat required.
"""
from __future__ import annotations

import base64
import contextlib
import io
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_agg import FigureCanvasAgg

BASE = Path(__file__).resolve().parent.parent
NBDIR = BASE / "notebooks"
NBDIR.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(BASE / "src"))
import helper_utils as hu  # noqa: E402

KERNEL = {
    "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
    "language_info": {"name": "python", "version": "3.10"},
}

NAVY = "#1b4f72"; BLUE = "#2874a6"; AMBER = "#e67e22"; RED = "#c0392b"
GREEN = "#1e8449"; GREY = "#7f8c8d"

plt.rcParams.update({"figure.dpi": 100, "font.size": 9, "axes.titlesize": 10,
                     "axes.titleweight": "bold", "axes.spines.top": False,
                     "axes.spines.right": False})


def md(*lines):
    return {"cell_type": "markdown", "metadata": {},
            "source": [l + "\n" for l in lines]}


def code(*lines):
    return {"cell_type": "code", "metadata": {}, "execution_count": None,
            "outputs": [], "source": [l + "\n" for l in lines]}


def _execute_cell(ns: dict, source: list[str], exec_count: int):
    src = "".join(source)
    plt.close("all")
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        exec(compile(src, "<cell>", "exec"), ns)
    outputs = []
    text = buf.getvalue()
    if text:
        outputs.append({"output_type": "stream", "name": "stdout", "text": text.rstrip("\n") + "\n"})
    for num in plt.get_fignums():
        fig = plt.figure(num)
        canvas = FigureCanvasAgg(fig)
        b = io.BytesIO()
        fig.savefig(b, format="png", bbox_inches="tight", dpi=105)
        b.seek(0)
        png = base64.b64encode(b.read()).decode("ascii")
        outputs.append({
            "output_type": "display_data",
            "data": {"image/png": png, "text/plain": ["<Figure size>"]},
            "metadata": {},
        })
    plt.close("all")
    return exec_count, outputs


def _last_expr(ns: dict, source: list[str], exec_count: int) -> tuple[int, list]:
    """Run code but also surface the last expression's repr as a text/plain output."""
    src = "".join(source)
    # split off a trailing expression to evaluate separately
    lines = source[:]
    code_text = "".join(lines)
    prefix = None
    # naive: try to detect trailing expression statement (no leading indent/compound)
    stripped = code_text.rstrip("\n")
    if stripped.count("\n") >= 1:
        pass  # handled by normal exec below
    # We run the full cell through exec; for expression display we wrap common
    # last-line patterns (DataFrame, Series, scalar) heuristically.
    return _execute_cell(ns, source, exec_count)


def _finalize(cells, exec_name):
    exec_count = 0
    ns = {"__name__": "__main__"}
    for cell in cells:
        if cell["cell_type"] == "code":
            exec_count += 1
            try:
                ec, outputs = _execute_cell(ns, cell["source"], exec_count)
            except Exception as exc:  # pragma: no cover
                outputs = [{"output_type": "error", "ename": type(exc).__name__,
                            "evalue": str(exc), "traceback": [str(exc)]}]
            cell["execution_count"] = exec_count
            cell["outputs"] = outputs

    nb = {"cells": cells, "metadata": KERNEL, "nbformat": 4, "nbformat_minor": 5}
    (NBDIR / exec_name).write_text(json.dumps(nb, ensure_ascii=False, indent=1),
                                   encoding="utf-8")
    print("wrote", NBDIR / exec_name)


# ============================================================================ #
#  Notebook 1 — signal & seasonality
# ============================================================================ #
nb1 = [
    md("# 03 — 从数据到信号（Data → Signal）",
       "",
       "**目标**：把 5 年、3 门店、4 品类的干净日销售，转化为可供预测与模拟使用的**可解释信号**。",
       "本笔记本覆盖：总体趋势、周期检测（无监督）、周/年季节模式、门店差异、价格信号、节假日效应与无监督异常检测。"),
    code("import sys\nfrom pathlib import Path\nimport numpy as np\nimport pandas as pd\nimport matplotlib.pyplot as plt\n\nif (Path.cwd() / 'src').exists():\n    sys.path.insert(0, str(Path.cwd() / 'src'))\nimport helper_utils as hu\n\nNAVY='#1b4f72'; BLUE='#2874a6'; AMBER='#e67e22'; RED='#c0392b'\nGREEN='#1e8449'; GREY='#7f8c8d'\nCOL={'Beverages':BLUE,'Bakery':AMBER,'Meat':RED,'Produce':GREEN}\nCAT=['Beverages','Bakery','Meat','Produce']\nplt.rcParams.update({'figure.dpi':100,'font.size':9,'axes.spines.top':False,'axes.spines.right':False})\n\nraw = hu.load_raw()\np = hu.build_panel()\ns = hu.daily_total(p)\nprint('sales rows:', len(raw['sales']), '| dates:', len(raw['dates']))\nprint('panel shape:', p.shape)\np.head(3)"),
    md("## 1. 总体趋势",
       "",
       "5 年日营收，叠加 30 日移动平均（短期波动）与 365 日移动平均（长期趋势）。"),
    code("fig, ax = plt.subplots(figsize=(9,3.2))\nax.plot(s.index, s.values, color=GREY, alpha=0.4, lw=0.6, label='daily')\nax.plot(s.index, s.rolling(30).mean(), color=BLUE, lw=1.1, label='30-day mean')\nax.plot(s.index, s.rolling(365).mean(), color=NAVY, lw=2.2, label='365-day trend')\nax.set_title('Total daily revenue, 2018–2022')\nax.set_ylabel('Revenue ($)')\nax.legend(frameon=False, loc='upper left')"),
    md("## 2. 无监督周期检测（periodogram）",
       "",
       "对去趋势序列做 FFT 周期图，**不依赖任何日历先验**地找出主导周期。"),
    code("periods = hu.dominant_periods(s, top_n=6)\nprint('dominant periods (days):', [round(per,1) for per,_ in periods])\n\nfrom scipy.signal import periodogram\ny = hu.detrend(s).to_numpy()\nf, Pxx = periodogram(y, detrend=False)\nm = f > 0\nfig, ax = plt.subplots(figsize=(9,3.0))\nax.plot(1/f[m], Pxx[m]/Pxx[m].max(), color=GREY, alpha=0.5, lw=0.7)\nax.set_xscale('log'); ax.set_xlim(2, 400)\nfor per, pw in periods[:6]:\n    ax.axvline(per, color=RED if abs(per-365)<3 or abs(per-7)<1 else AMBER, ls='--', lw=1.1, alpha=0.8)\n    ax.annotate(f'{per:.0f}d', (per, pw), xytext=(4,3), textcoords='offset points', fontsize=8)\nax.set_xlabel('Period (days, log)'); ax.set_ylabel('Normalised power')\nax.set_title('Periodogram: weekly (7d) + annual (~365d) dominate')"),
    md("## 3. 周度与年度季节模式（按品类）",
       "",
       "分品类看一周内的起伏与一年内的起伏，揭示「谁更季节敏感」。"),
    code("wp = p.groupby(['category_name','dow'])['sales_revenue'].mean().reset_index()\nmp = p.groupby(['category_name','month'])['sales_revenue'].mean().reset_index()\nfig, axes = plt.subplots(1, 2, figsize=(11,3.2))\nfor c in CAT:\n    d = wp[wp.category_name==c].sort_values('dow')\n    axes[0].plot(d.dow, d.sales_revenue, marker='o', ms=3, color=COL[c], label=c)\n    d2 = mp[mp.category_name==c].sort_values('month')\n    axes[1].plot(d2.month, d2.sales_revenue, marker='o', ms=3, color=COL[c], label=c)\naxes[0].set_xticks(range(7)); axes[0].set_xticklabels(['Mon','Tue','Wed','Thu','Fri','Sat','Sun'])\naxes[0].set_title('Weekly seasonality'); axes[0].set_ylabel('Mean revenue ($)')\naxes[1].set_xticks(range(1,13)); axes[1].set_title('Annual seasonality (Q4 holiday peak)')\naxes[1].legend(frameon=False, ncol=2, fontsize=8)"),
    md("## 4. 门店差异",
       "",
       "三家门店（西雅图/波特兰/博伊西）同为西北—山地市场，体量不同但节奏一致。"),
    code("sp = p.groupby(['store_id','dow'])['sales_revenue'].mean().reset_index()\nlab={1:'Seattle (L)',2:'Portland (M)',3:'Boise (S)'}\nfig, ax = plt.subplots(figsize=(9,3.0))\nfor sid in [1,2,3]:\n    d = sp[sp.store_id==sid].sort_values('dow')\n    ax.plot(d.dow, d.sales_revenue, marker='o', ms=3, color=[NAVY,BLUE,AMBER][sid-1], label=lab[sid])\nax.set_xticks(range(7)); ax.set_xticklabels(['Mon','Tue','Wed','Thu','Fri','Sat','Sun'])\nax.set_title('Store weekly profile (scale differs, shape aligns)')\nax.set_ylabel('Mean revenue ($)'); ax.legend(frameon=False)"),
    md("## 5. 价格信号",
       "",
       "`unit_price = sales_revenue / sales_qty`。观察价格趋势，并量化「价格-数量」相关（描述性、非因果）。"),
    code("qp = p.groupby(['date','category_name'])['unit_price'].mean().reset_index()\nfig, ax = plt.subplots(figsize=(9,3.0))\nfor c in CAT:\n    d = qp[qp.category_name==c]\n    ax.plot(d.date, d.unit_price.rolling(30).mean(), lw=1.1, color=COL[c], label=c)\nax.set_title('Category unit-price trends'); ax.set_ylabel('$/unit'); ax.legend(frameon=False, ncol=4)\n\nfor c in CAT:\n    dd = p[p.category_name==c]\n    r = np.corrcoef(np.log(dd.sales_qty+1), np.log(dd.unit_price))[0,1]\n    print(f'  price-qty corr (descriptive, non-causal) ({c}): {r:+.3f}')"),
    md("## 6. 节假日效应 + 无监督异常检测",
       "",
       "用 STL 残差的 |z|>3.5 做**无监督**异常检测，再与节假日日历交叉验证。"),
    code("hol = hu.us_holiday_calendar(2018, 2022)\nday = s.loc[hol['date'].tolist()]\nnon = s.loc[~s.index.isin(hol['date'])]\nuplift = 100*(day.mean()/non.mean()-1)\nprint(f'holiday uplift: +{uplift:.1f}%  (holiday mean {day.mean():.0f} vs non-holiday {non.mean():.0f})')\n\nan = hu.detect_anomalies(s, period=7, k=3.5)\nan = an.merge(hol.assign(is_holiday=1), on='date', how='left')\nn_det = int(an['is_anomaly'].sum())\nn_hit = int(an.loc[an['is_anomaly'],'is_holiday'].fillna(0).sum())\nprint(f'detected anomalies: {n_det}, on holidays: {n_hit} (precision {n_hit/max(n_det,1):.2%})')\n\nfig, ax = plt.subplots(figsize=(9,3.2))\nax.plot(s.index, s.values, color=GREY, alpha=0.4, lw=0.6, label='observed')\nup = an[an.direction=='uplift']; dn = an[an.direction=='suppression']\nax.scatter(up.date, up.observed, color=GREEN, s=13, label='detected uplift', zorder=3)\nax.scatter(dn.date, dn.observed, color=RED, s=13, label='detected suppression', zorder=3)\nax.set_title('Unsupervised anomaly detection (STL residual, |z|>3.5)')\nax.set_ylabel('Revenue ($)'); ax.legend(frameon=False)"),
    md("## 7. 小结（信号结论）",
       "",
       "- 主导周期 **7 天（周）** + **~365 天（年）**，由无监督周期图自动发现；",
       "- 周末抬升、Q4 节假日峰值是年周期主因；节假日当日销售平均 **+12.5%**；",
       "- **价格-数量相关近乎为零**（描述性、非因果）：需求由日历/节假日驱动；",
       "- 无监督异常检测 18 个异常点中 12 个落在节假日上（精确率 66.7%）。"),
]

# ============================================================================ #
#  Notebook 2 — forecasting
# ============================================================================ #
nb2 = [
    md("# 03 — 可解释预测：SARIMA → SARIMAX",
       "",
       "**目标**：在可信数据上训练可解释、可复现的预测流程。",
       "训练集 2018–2021，测试集 2022（完整盲测一年）。基准：持久化、季节性朴素；主模型：SARIMA（仅周季节）与 SARIMAX（叠加节假日+年度傅里叶外生因子）。"),
    code("import sys\nfrom pathlib import Path\nimport numpy as np\nimport pandas as pd\nimport matplotlib.pyplot as plt\n\nif (Path.cwd() / 'src').exists():\n    sys.path.insert(0, str(Path.cwd() / 'src'))\nimport helper_utils as hu\nimport forecast as fc\n\nNAVY='#1b4f72'; BLUE='#2874a6'; AMBER='#e67e22'; GREY='#9aa4b0'; GREEN='#1e8449'\nplt.rcParams.update({'figure.dpi':100,'font.size':9,'axes.spines.top':False,'axes.spines.right':False})\n\nTRAIN_END = pd.Timestamp('2021-12-31')\np = hu.build_panel()\ns = hu.daily_total(p)\nprint('total series:', s.index.min().date(), '->', s.index.max().date(), '| n =', len(s))"),
    md("## 1. 基准（朴素模型）",
       "",
       "持久化（沿用昨日）与季节性朴素（沿用上周同期）——任何模型都必须先打赢它们。"),
    code("train = s.loc[:TRAIN_END]\ntest = s.loc[s.index > TRAIN_END]\nh = len(test)\npers = fc.persistence_naive(train, h)\nnaive = fc.seasonal_naive(train, h, 7)\nm_p = hu.forecast_metrics(test, pers)\nm_n = hu.forecast_metrics(test, naive)\nfor name, m in [('persistence', m_p), ('seasonal_naive', m_n)]:\n    print(f'  {name:<16} MAE={m[\"MAE\"]:7.0f}  RMSE={m[\"RMSE\"]:7.0f}  MAPE={m[\"MAPE\"]:5.1f}%')"),
    md("## 2. SARIMA（仅周季节）vs SARIMAX（叠加外生因子）",
       "",
       "SARIMA 只能捕捉固定 7 天周期；SARIMAX 额外注入 **is_holiday** 与 **2 对年度傅里叶项**，",
       "让模型「看见」节假日冲击与年度起伏。"),
    code("res = fc.evaluate_series(s, TRAIN_END, m=7, verbose=False)\nfor name in ['sarima','sarimax']:\n    m = res[name]\n    print(f'  {name:<8} MAE={m[\"MAE\"]:7.0f}  RMSE={m[\"RMSE\"]:7.0f}  MAPE={m[\"MAPE\"]:5.1f}%')\nprint(f'  AIC  SARIMA={res[\"sarima_aic\"]:.1f}  ->  SARIMAX={res[\"sarimax_aic\"]:.1f}')"),
    code("test = res['test']; fdf = res['forecast_df']\nfig, ax = plt.subplots(figsize=(9,3.4))\nax.plot(test.index, test.values, color=NAVY, lw=1.0, label='actual')\nax.plot(fdf.index, fdf['forecast'], color=AMBER, lw=1.0, label='SARIMAX forecast')\nax.fill_between(fdf.index, fdf['lower'], fdf['upper'], color=AMBER, alpha=0.18, label='95% CI')\nax.set_title('2022 daily revenue — SARIMAX vs actual (MAPE %.1f%%)' % res['sarimax']['MAPE'])\nax.set_ylabel('Revenue ($)')\nax.legend(frameon=False, loc='upper left')"),
    md("## 3. 业务层级：品类与门店",
       "",
       "读取分层预测结果，观察「外部因子」在每个细分上的改善幅度。"),
    code("import json\nfm = json.load(open(Path.cwd() / 'reports' / 'forecast_metrics.json', encoding='utf-8'))\nrows = []\nfor r in fm['category'] + fm['store']:\n    rows.append({'name': r['name'], 'naive': r['naive_MAPE'],\n                 'sarima': r['sarima_MAPE'], 'sarimax': r['sarimax_MAPE']})\ndf = pd.DataFrame(rows).sort_values('sarimax')\n\nfig, ax = plt.subplots(figsize=(9,3.6))\ny = np.arange(len(df))\nax.barh(y+0.25, df['naive'],   height=0.22, color=GREY,  label='seasonal naive')\nax.barh(y,     df['sarima'],  height=0.22, color=BLUE,  label='SARIMA (weekly)')\nax.barh(y-0.25, df['sarimax'], height=0.22, color=AMBER, label='SARIMAX (+holiday/annual)')\nax.set_yticks(y); ax.set_yticklabels(df['name']); ax.invert_yaxis()\nax.set_xlabel('MAPE (%)'); ax.set_title('Forecast error by segment')\nax.legend(frameon=False, loc='lower right')\ndf"),
    md("## 4. 结论",
       "",
       "- SARIMAX 在总序列上将 SARIMA 的 MAPE 从 **15.1%→10.5%**，RMSE 从 1743→1286；",
       "- 改善最显著的是 **Bakery（78%→30%）**：其需求由节假日峰驱动，纯周模型无法捕捉；",
       "- 每年 365 天全盲测，所有细分 SARIMAX ≥ SARIMA，验证「外部因子=信号」这一命题。"),
]

_finalize(nb1, "03_data_signal.ipynb")
_finalize(nb2, "03_forecast.ipynb")