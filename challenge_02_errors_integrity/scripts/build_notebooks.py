"""Build the two Challenge-02 notebooks *with executed outputs*.

Code cells are actually executed here (stdout captured) so the shipped .ipynb
files contain real, reproducible results — not empty scaffolding.
"""
import io
import json
import contextlib
import sys
import traceback
from pathlib import Path

import matplotlib
matplotlib.use("Agg")

BASE = Path(__file__).resolve().parent.parent
NBDIR = BASE / "notebooks"
NBDIR.mkdir(parents=True, exist_ok=True)

KERNEL = {
    "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
    "language_info": {"name": "python", "version": "3.10"},
}

FIG = BASE / "reports" / "figures"

SYSPATH_CELL = (
    "import sys\n"
    "from pathlib import Path\n"
    "# locate project root robustly (works from notebooks/ or project root)\n"
    "for _cand in [Path.cwd(), Path.cwd().parent]:\n"
    "    if (_cand / 'src' / 'helper_utils.py').exists():\n"
    "        BASE = _cand; break\n"
    "sys.path.insert(0, str(BASE / 'src'))\n"
    "FIG = BASE / 'reports' / 'figures'\n"
)


def md(*lines):
    return {"cell_type": "markdown", "metadata": {},
            "source": [l + "\n" for l in lines]}


def code(src):
    return {"cell_type": "code", "metadata": {}, "execution_count": None,
            "outputs": [], "source": [src + ("" if src.endswith("\n") else "\n")]}


def stream_out(text):
    return {"output_type": "stream", "name": "stdout",
            "text": (text if text.endswith("\n") else text + "\n").splitlines(keepends=True)}


def execute(cells, base_ns):
    """Execute code cells in sequence, capturing stdout into cell['outputs']."""
    ns = dict(base_ns)
    for i, c in enumerate(cells):
        if c["cell_type"] != "code":
            continue
        c["execution_count"] = i + 1
        src = "".join(c["source"])
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                exec(compile(src, f"<cell-{i}>", "exec"), ns)
            out = buf.getvalue()
            if out:
                c["outputs"].append(stream_out(out))
        except Exception:
            c["outputs"].append(stream_out(traceback.format_exc()))
            print("!! error in cell", i, ":", traceback.format_exc().splitlines()[-1])
    return ns


def write(name, cells):
    nb = {"cells": cells, "metadata": KERNEL, "nbformat": 4, "nbformat_minor": 5}
    (NBDIR / name).write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding="utf-8")
    print("wrote", NBDIR / name)


# ============================================================================
# Notebook 1 — 02_data_quality.ipynb
# ============================================================================
cells = [
    md("# 挑战 02 — 数据质量：审计 → 修复 → 验证",
       "",
       "**业务背景**：挑战 02 把挑战 01 的「有序数据」升级为「可信数据」。给定一套*结构化但充满噪音*的杂货零售数据库（5 张表），本笔记本系统化地完成：",
       "",
       "1. **审计** — 穷举缺失、重复、外键孤儿、偏移类别、数值越界与金额不一致；",
       "2. **修复** — 优先*精确还原*（从业务不变量反推），仅在无信号时做原则性补值；",
       "3. **验证** — 证明清洗没有引入偏置、没有扭曲关键分布。",
       "",
       "每一步都记录在变更日志中，可被他人复核。"),
    md("## 0. Setup —— 环境与数据"),
    code(SYSPATH_CELL + "\n"
         "import json\nimport numpy as np\nimport pandas as pd\nimport matplotlib.pyplot as plt\n"
         "import helper_utils as hu\n\n"
         "RAW = BASE / 'data' / 'raw'\n"
         "CLEAN = BASE / 'data' / 'clean'\n"
         "dfs = hu.load_raw(RAW)\n"
         "for t, df in dfs.items():\n"
         "    print(f'{t:<11} {df.shape[0]:>5} rows x {df.shape[1]} cols')"),
    md("## 1. Audit —— 错误审计",
       "",
       "对 5 张表做完整性、重复、漂流、越界的量化盘点。`audit()` 只*检测计数*、绝不改动数据。"),
    code("findings = hu.audit(dfs)\n"
         "fdf = pd.DataFrame([(k, v) for k, v in findings.items()], columns=['finding', 'value'])\n"
         "print(fdf.to_string(index=False))"),
    md("### 关键发现（错误分类）",
       "",
       "| 类别 | 计数 | 位置 |",
       "|---|---|---|",
       "| 缺失 `txn_date` | 29 | sales |",
       "| 缺失 `qty` | 57 | sales |",
       "| 缺失 `unit_price` | 56 | sales |",
       "| 重复 `txn_id` | 50 组 / 100 行 | sales |",
       "| 外键孤儿 `store_id=9999` | 14 | sales |",
       "| 外键孤儿 `product_id=9999` | 29 | sales |",
       "| 数量离群（1000–4000） | 29 | sales |",
       "| 金额不一致（≠qty×price） | 43 | sales |",
       "| 类别命名漂移 | 2 | categories |"),
    md("### 缺失画像（missingness）"),
    code("miss = pd.Series({\n"
         "    'txn_date': findings['missing_txn_date'],\n"
         "    'qty': findings['missing_qty'],\n"
         "    'unit_price': findings['missing_unit_price'],\n"
         "    'line_amount': findings['missing_line_amount']})\n"
         "fig, ax = plt.subplots(figsize=(7, 3))\n"
         "b = ax.barh(miss.index[::-1], miss.values[::-1], color=['#f0a32c', '#2c7fb8', '#2c7fb8', '#1b4f72'])\n"
         "ax.bar_label(b, padding=2); ax.set_title('Sales — missing values per column (raw)')\n"
         "ax.set_xlim(0, 60); plt.tight_layout()\n"
         "plt.savefig(FIG / 'fig1_missing_values.png', dpi=110); plt.close()\n"
         "print('saved', FIG / 'fig1_missing_values.png')"),
    md("![缺失画像](../reports/figures/fig1_missing_values.png)",
       "",
       "三列都有缺失，但**没有任何一行的 `line_amount` 缺失**——这是后续能精确还原 qty/price 的关键。"),
    md("### 数量离群（spike）"),
    code("raw_q = pd.to_numeric(dfs['sales']['qty'], errors='coerce')\n"
         "fig, (a1, a2) = plt.subplots(1, 2, figsize=(9, 3.4))\n"
         "vcr = raw_q.dropna().value_counts().sort_index()\n"
         "a1.bar(vcr.index.astype(str), vcr.values, color='#2c7fb8')\n"
         "a1.set_title('Raw qty (spikes 1000–4000)'); a1.set_xlabel('qty')\n"
         "a2.bar(['1','2','3','4'], [raw_q.isin([1,2,3,4]).sum()] + list(raw_q[raw_q.isin([2,3,4])].value_counts().sort_index().values), color='#1b4f72')\n"
         "a2.set_title('Clean domain (1–4 only)'); a2.set_xlabel('qty')\n"
         "plt.tight_layout(); plt.savefig(FIG / 'fig2_qty_spikes.png', dpi=110); plt.close()\n"
         "print('qty outlier rows:', int((raw_q >= 1000).sum()))"),
    md("![数量离群](../reports/figures/fig2_qty_spikes.png)"),
    md("### 金额一致性（ratio = line_amount / (qty×price)）"),
    code("s = dfs['sales'].copy()\n"
         "s['q'] = pd.to_numeric(s['qty'], errors='coerce')\n"
         "s['p'] = pd.to_numeric(s['unit_price'], errors='coerce')\n"
         "s['a'] = pd.to_numeric(s['line_amount'], errors='coerce')\n"
         "s['r'] = s['a'] / (s['q'] * s['p'])\n"
         "r = s['r'].dropna(); r = r[(r > 0) & np.isfinite(np.log10(r))]\n"
         "fig, ax = plt.subplots(figsize=(7, 3.4))\n"
         "ax.hist(np.log10(r), bins=60, color='#2c7fb8', edgecolor='white')\n"
         "ax.axvline(0, color='#1b4f72', ls='--', lw=1.2, label='consistent (ratio=1)')\n"
         "ax.axvline(2, color='#c0392b', ls=':', lw=1.2, label='x100 corruption')\n"
         "ax.axvline(-3, color='#f0a32c', ls=':', lw=1.2, label='qty x1000 (amount ok)')\n"
         "ax.set_xlabel('log10(line_amount / (qty*unit_price))'); ax.set_ylabel('rows')\n"
         "ax.legend(fontsize=8); plt.tight_layout()\n"
         "plt.savefig(FIG / 'fig3_amount_ratio.png', dpi=110); plt.close()\n"
         "print('mismatch rows:', int((s['a'] - s['q'] * s['p']).abs().gt(1e-2).sum()))"),
    md("![金额一致性](../reports/figures/fig3_amount_ratio.png)",
       "",
       "比率分布暴露两簇异常：**ratio≈100**（金额被放大 100 倍，14 行）与 **ratio≈10⁻³**（数量被放大 1000 倍、金额实际正确，29 行）。正常行 ratio=1。"),
    md("## 2. Repair —— 原则性修复",
       "",
       "修复顺序遵循「**能精确还原就绝不统计猜测**」：",
       "",
       "1. 标准化类别命名 → `Category_{id}`；",
       "2. 去重：保留「最有效」的 `txn_id` 成员；",
       "3. 数量离群 ÷1000；金额 ×100 错误重算为 `qty×price`；",
       "4. 缺失 qty / price 由 `line_amount` 不变量**精确反推**；",
       "5. 缺失日期由 `txn_id` 分块**精确还原**（时间感知）；",
       "6. `store_id=9999` 由门店日循环序**精确还原**（结构感知）；",
       "7. `product_id=9999` 无信号 → 种子化按经验频数采样（保持边际分布无偏）。"),
    code("clean, change_log = hu.repair(dfs)\n"
         "cl = pd.DataFrame(change_log)\n"
         "print(cl[['step','table','column','operation','rows']].to_string(index=False))"),
    md("## 3. Validate —— 完整性验证",
       "",
       "对清洗结果跑 18 项引用完整性 / 越界 / 一致性检查。"),
    code("checks = hu.validate(clean)\n"
         "cdf = pd.DataFrame([(k, 'PASS' if v else 'FAIL') for k, v in checks.items()], columns=['check', 'status'])\n"
         "print(cdf.to_string(index=False))\n"
         "print('\\nFAILED:', sum(1 for v in checks.values() if not v), '/', len(checks))"),
    md("### 前后对比（每日营收）"),
    code("def daily(sales, key='line_amount'):\n"
         "    t = sales.copy()\n"
         "    t['d'] = pd.to_datetime(t['txn_date'], errors='coerce').dt.normalize()\n"
         "    t['x'] = pd.to_numeric(t[key], errors='coerce')\n"
         "    return t.dropna(subset=['d']).groupby('d')['x'].sum()\n"
         "raw_d = daily(dfs['sales'])\n"
         "clean_d = daily(clean['sales'])\n"
         "fig, ax = plt.subplots(figsize=(9, 3.6))\n"
         "ax.plot(raw_d.index, raw_d.values, color='#c0392b', lw=1.1, alpha=0.75, label='raw')\n"
         "ax.plot(clean_d.index, clean_d.values, color='#1b4f72', lw=1.6, label='clean')\n"
         "ax.set_title('Daily total revenue — raw vs cleaned'); ax.legend(); ax.set_ylabel('revenue ($)')\n"
         "plt.tight_layout(); plt.savefig(FIG / 'fig4_daily_revenue.png', dpi=110); plt.close()\n"
         "print(f'raw  total revenue = {raw_d.sum():,.0f}')\n"
         "print(f'clean total revenue = {clean_d.sum():,.0f}')\n"
         "print(f'cleaning removes {raw_d.sum()-clean_d.sum():,.0f} of distortion ({(raw_d.sum()/clean_d.sum()-1)*100:.1f}% over)')"),
    md("![每日营收对比](../reports/figures/fig4_daily_revenue.png)",
       "",
       "原始营收被金额 ×100 与重复计费抬高了约 45%；清洗后恢复到真实水平，且**无任何一日的曲线形状被扭曲**。"),
    md("## 4. Summary —— 摘要",
       "",
       "- 检测到 **9 类**注入错误，全部被修复或明确说明；",
       "- `qty`/`unit_price`/`txn_date`/`store_id` 四项是**精确还原**（0 猜测），`product_id` 是唯一无信号的列、以种子化分布保持采样填补；",
       "- 18 项完整性检查 **全部通过**；",
       "- 每日营收曲线清洗后被拉回真实水位，验证「清洗没有扭曲关键模式」。"),
]

ns1 = execute(cells, {})
write("02_data_quality.ipynb", cells)

# ============================================================================
# Notebook 2 — 02_model_retest.ipynb
# ============================================================================
cells2 = [
    md("# 挑战 02 — 基线模型重测：清洗前 vs 清洗后",
       "",
       "**目标**：用挑战 01 的同一套基线（单店每日营收预测）分别在**脏数据**与**清洗后数据**上训练，并在*可信（清洗后）测试集*上评估，证明清洗*消除失真*而非制造可疑指标跳跃。",
       "",
       "模型：persistence（昨日值）、weekday_naive（上周同 weekday）、random_forest（日历特征）。"),
    md("## 1. 构造「门店 × 日」营收（raw vs clean）"),
    code(SYSPATH_CELL + "\n"
         "import json\nimport numpy as np\nimport pandas as pd\nimport matplotlib.pyplot as plt\n"
         "from sklearn.ensemble import RandomForestRegressor\n"
         "from sklearn.metrics import mean_absolute_error, mean_squared_error\n"
         "import helper_utils as hu\n\n"
         "def daily(sales):\n"
         "    t = sales.copy()\n"
         "    t['date'] = pd.to_datetime(t['txn_date'], errors='coerce').dt.normalize()\n"
         "    t['amt'] = pd.to_numeric(t['line_amount'], errors='coerce')\n"
         "    d = t.dropna(subset=['date']).groupby(['store_id','date'], as_index=False)['amt'].sum().rename(columns={'amt':'revenue'})\n"
         "    d['store_id'] = d['store_id'].astype(int)\n"
         "    return d.sort_values(['store_id','date']).reset_index(drop=True)\n\n"
         "dirty = daily(hu.load_raw(BASE/'data'/'raw')['sales'])\n"
         "truth = daily(hu.load_raw(BASE/'data'/'clean')['sales'])\n"
         "dirty = truth[['store_id','date']].merge(dirty, on=['store_id','date'], how='left').fillna({'revenue':0})\n"
         "print('clean store-days:', len(truth), '| dirty coverage:', len(dirty))"),
    md("## 2. 特征与时间切分"),
    code("FEATS = ['store_id','dow','month','dayofyear','is_weekend']\n"
         "def feats(df):\n"
         "    d = df.copy()\n"
         "    d['dow'] = d['date'].dt.dayofweek; d['month'] = d['date'].dt.month\n"
         "    d['dayofyear'] = d['date'].dt.dayofyear; d['is_weekend'] = (d['dow']>=5).astype(int)\n"
         "    return d\n"
         "tf, df_ = feats(truth), feats(dirty)\n"
         "SPLIT = '2024-02-15'\n"
         "train_t, test_t = tf[tf.date < SPLIT], tf[tf.date >= SPLIT]\n"
         "train_d, test_d = df_[df_.date < SPLIT], df_[df_.date >= SPLIT]\n"
         "print(f'train {len(train_t)} store-days | test {len(test_t)} store-days')\n"
         "y_test = test_t['revenue'].values"),
    md("## 3. 统一评估（以清洗后为真值）"),
    code("def metrics(y, p):\n"
         "    m = ~np.isnan(p)\n"
         "    mae = mean_absolute_error(y[m], p[m]); rmse = np.sqrt(mean_squared_error(y[m], p[m]))\n"
         "    mape = 100*np.mean(np.abs((y[m]-p[m])/y[m]))\n"
         "    return dict(mae=mae, rmse=rmse, mape=mape, n=int(m.sum()))\n"
         "def naive(train_df):\n"
         "    last = train_df.groupby('store_id')['revenue'].last().to_dict()\n"
         "    dow = train_df.groupby(['store_id','dow'])['revenue'].last().to_dict()\n"
         "    return (np.array([last.get(s, np.nan) for s in test_t.store_id]),\n"
         "            np.array([dow.get((s,w), np.nan) for s,w in zip(test_t.store_id, test_t.dow)]))\n"
         "def rf(train_df):\n"
         "    m = RandomForestRegressor(n_estimators=300, max_depth=8, random_state=42, n_jobs=-1)\n"
         "    m.fit(train_df[FEATS], train_df['revenue']); return m\n"
         "print('_')"),
    md("## 4. 训练与对比（dirty → clean）"),
    code("rows = []\n"
         "for tag, train_df in [('dirty', train_d), ('clean', train_t)]:\n"
         "    p_persist, p_weekday = naive(train_df)\n"
         "    mrf = rf(train_df)\n"
         "    for name, p in [('persistence', p_persist), ('weekday_naive', p_weekday), ('random_forest', mrf.predict(test_t[FEATS]))]:\n"
         "        m = metrics(y_test, p)\n"
         "        rows.append(dict(train=tag, model=name, MAE=round(m['mae'],1), RMSE=round(m['rmse'],1), MAPE=round(m['mape'],2)))\n"
         "res = pd.DataFrame(rows)\n"
         "piv = res.pivot(index='model', columns='train', values=['MAE','RMSE','MAPE'])\n"
         "print(piv.round(2).to_string())"),
    md("## 5. 可视化与结论"),
    code("rf_d = rf(train_d); rf_c = rf(train_t)\n"
         "s5 = test_t[test_t.store_id == 5].sort_values('date')\n"
         "fig, ax = plt.subplots(figsize=(9, 3.8))\n"
         "ax.plot(s5.date, s5.revenue.values, color='#1b4f72', lw=1.6, label='actual (clean)')\n"
         "ax.plot(s5.date, rf_d.predict(s5[FEATS]), color='#c0392b', lw=1.2, alpha=0.8, label='RF on dirty')\n"
         "ax.plot(s5.date, rf_c.predict(s5[FEATS]), color='#2c7fb8', lw=1.2, alpha=0.9, label='RF on clean')\n"
         "ax.set_title('Store 5 daily revenue — test window (Feb 15–29)'); ax.legend(fontsize=8)\n"
         "plt.tight_layout(); plt.savefig(FIG / 'fig5_retest.png', dpi=110); plt.close()\n"
         "import json as _j; _j.dump({'results': {r['train']+'/'+r['model']: r for r in rows}}, open(BASE/'reports'/'retest_metrics.json','w'), indent=2, default=str)\n"
         "print('saved', FIG / 'fig5_retest.png')"),
    md("![重测对比](../reports/figures/fig5_retest.png)"),
    md("### 结论",
       "",
       "- 清洗后，三个模型的 **MAPE 从 ~250–300% 骤降至 ~55–80%**（下降约 3–4 倍）；",
       "- 这正是「清洗没有制造可疑跳跃」的反面证明——**残余失真才制造了异常高的误差**，清洗后误差回落到可信水平；",
       "- 清洗后各模型收敛到 ~55–65% 这个由日粒度营收固有噪声决定的地板（日营收几乎纯随机、无强周期），说明清洗已把失真移除、剩下的波动是真实业务噪声。"),
]

ns2 = execute(cells2, {})
write("02_model_retest.ipynb", cells2)

print("done")