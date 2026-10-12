"""Build slides/presentation_deck.pptx (7 slides, 16:9) for Challenge 02."""
from pathlib import Path
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

BASE = Path(__file__).resolve().parent.parent
FIG = BASE / "reports" / "figures"
OUT = BASE / "slides" / "presentation_deck.pptx"
OUT.parent.mkdir(parents=True, exist_ok=True)

NAVY = RGBColor(0x1B, 0x4F, 0x72)
BLUE = RGBColor(0x2C, 0x7F, 0xB8)
INK = RGBColor(0x1A, 0x23, 0x32)
SUB = RGBColor(0x5B, 0x64, 0x72)
AMBER = RGBColor(0xF0, 0xA3, 0x2C)
RED = RGBColor(0xC0, 0x39, 0x2B)
LIGHT = RGBColor(0xF6, 0xF8, 0xFA)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
PALE = RGBColor(0xD6, 0xEA, 0xF8)

prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)
BLANK = prs.slide_layouts[6]
SW, SH = prs.slide_width, prs.slide_height


def slide():
    return prs.slides.add_slide(BLANK)


def rect(s, x, y, w, h, color):
    shp = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, y, w, h)
    shp.fill.solid(); shp.fill.fore_color.rgb = color
    shp.line.fill.background(); shp.shadow.inherit = False
    return shp


def text(s, x, y, w, h, runs, size=18, color=INK, bold=False, align=PP_ALIGN.LEFT,
         font="Segoe UI", anchor=MSO_ANCHOR.TOP):
    tb = s.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame; tf.word_wrap = True; tf.vertical_anchor = anchor
    if isinstance(runs, str):
        runs = [[(runs, dict(size=size, color=color, bold=bold, font=font, align=align))]]
    first = True
    for para in runs:
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        p.alignment = para[0][1].get("align", align)
        for txt, st in para:
            r = p.add_run(); r.text = txt
            r.font.size = Pt(st.get("size", size))
            r.font.bold = st.get("bold", bold)
            r.font.color.rgb = st.get("color", color)
            r.font.name = st.get("font", font)
    return tb


def title_bar(s, title, sub=None):
    rect(s, 0, 0, SW, Inches(1.05), NAVY)
    text(s, Inches(0.55), Inches(0.16), SW - Inches(1.1), Inches(0.6),
         title, size=26, color=WHITE, bold=True, font="Segoe UI Semibold",
         anchor=MSO_ANCHOR.MIDDLE)
    if sub:
        text(s, Inches(0.55), Inches(0.72), SW - Inches(1.1), Inches(0.3),
             sub, size=12, color=PALE, font="Segoe UI")


def bullets(s, x, y, w, h, items, size=15):
    lines = []
    for it in items:
        head, rest = it if isinstance(it, tuple) else ("", it)
        lines.append([("• ", dict(size=size, color=BLUE, bold=True)),
                      (head, dict(size=size, color=INK, bold=True)),
                      (rest, dict(size=size, color=INK, bold=False))])
    text(s, x, y, w, h, lines)


def pic(s, path, x, y, w=None, h=None):
    return s.shapes.add_picture(str(path), x, y, width=w, height=h)


# 1 — Title ---------------------------------------------------------------
s = slide()
rect(s, 0, 0, SW, SH, NAVY)
rect(s, 0, Inches(4.9), SW, Inches(0.06), AMBER)
text(s, Inches(0.9), Inches(1.6), Inches(11.5), Inches(1.6),
     "挑战 02 · 从数据混乱到数据信心", size=40, color=WHITE, bold=True, font="Segoe UI Semibold")
text(s, Inches(0.9), Inches(2.9), Inches(11), Inches(1.0),
     "把结构化但混乱的零售数据，审计、修复、验证为可复现、可审计、AI 就绪的可信底座\n—— 错误 → 诚信",
     size=20, color=PALE)
for i, (v, l) in enumerate([("9", "类注入错误被枚举"),
                            ("4/5", "项精确还原（0 猜测）"),
                            ("18/18", "完整性校验通过"),
                            ("+44.9%", "营收虚高被移除")]):
    x = Inches(0.9 + i * 3.05)
    text(s, x, Inches(5.35), Inches(2.9), Inches(0.7), v, size=34, color=WHITE, bold=True)
    text(s, x, Inches(6.05), Inches(2.9), Inches(0.4), l, size=13, color=PALE)

# 2 — Objectives ----------------------------------------------------------
s = slide()
title_bar(s, "目标：让数据「可信」", "工作管道 vs 脆弱管道 —— 记录、检查、可复现")
bullets(s, Inches(0.55), Inches(1.5), Inches(6.4), Inches(5.2), [
    ("① 错误审计", " — 缺失、重复、孤儿外键、漂移类别、异常峰值"),
    ("② 完整性修复", " — 原则性修复，逐项给出理由"),
    ("③ 验证结果", " — 确认清洗不引入偏置、不扭曲分布"),
    ("④ 透明文档", " — 审计日志、变更摘要、可复现备注"),
], size=16)
rect(s, Inches(7.35), Inches(1.5), Inches(5.4), Inches(4.9), LIGHT)
text(s, Inches(7.7), Inches(1.75), Inches(4.8), Inches(0.5), "数据范围", size=18, color=NAVY, bold=True)
text(s, Inches(7.7), Inches(2.35), Inches(4.8), Inches(4.0), [
    [("5 张表", dict(size=14, color=INK, bold=True)), ("（products/vendors/stores/categories/sales）", dict(size=13, color=SUB))],
    [("sales", dict(size=13, color=INK, bold=True)), ("：2,859 交易，7 列，错误集中地", dict(size=13, color=SUB))],
    [("", dict(size=6, color=SUB))],
    [("维度表基本干净", dict(size=13, color=SUB)), ("；类别表有命名漂移", dict(size=13, color=RED))],
])

# 3 — Audit findings ------------------------------------------------------
s = slide()
title_bar(s, "审计：9 类注入错误", "仅检测计数，绝不改动数据")
rows = [
    ("缺失 txn_date / qty / unit_price", "29 / 57 / 56"),
    ("重复 txn_id（47 同 + 3 冲突）", "50 组 / 100 行"),
    ("外键孤儿 store_id / product_id = 9999", "14 / 29"),
    ("数量离群（1000–4000，金额却正确）", "29"),
    ("金额不一致（≠ qty×price）", "43"),
    ("类别命名漂移（Cat-One / category_2）", "2"),
]
y = 1.55
for name, cnt in rows:
    rect(s, Inches(0.7), Inches(y), Inches(7.6), Inches(0.72), LIGHT)
    text(s, Inches(1.0), Inches(y + 0.09), Inches(6.4), Inches(0.55), name, size=16, color=INK)
    text(s, Inches(7.9), Inches(y + 0.09), Inches(2.3), Inches(0.55), cnt, size=16, color=NAVY,
         bold=True, align=PP_ALIGN.RIGHT)
    y += 0.82
pic(s, FIG / "fig1_missing_values.png", Inches(8.7), Inches(1.55), w=Inches(4.2))

# 4 — Repair strategy -----------------------------------------------------
s = slide()
title_bar(s, "修复：精确还原优先，统计补值兜底")
bullets(s, Inches(0.55), Inches(1.45), Inches(6.3), Inches(5.4), [
    ("精确还原", " — 由业务不变量反推，0 猜测："),
    ("  qty / unit_price", " ← line_amount = qty×unit_price"),
    ("  txn_date", " ← txn_id → 日期的单调阶跃（时间感知）"),
    ("  store_id", " ← 每日门店 1→5 连续循环（结构感知）"),
    ("离群修正", " — qty ÷1000、金额重算 qty×price"),
    ("唯一无信号", " — product_id（与所有列不相关）"),
    ("  种子化比例抽样", " — 保持边际分布无偏"),
], size=15)
pic(s, FIG / "fig3_amount_ratio.png", Inches(7.1), Inches(1.6), w=Inches(5.6))

# 5 — Before/after --------------------------------------------------------
s = slide()
title_bar(s, "验证：清洗不扭曲关键模式")
pic(s, FIG / "fig4_daily_revenue.png", Inches(0.55), Inches(1.45), w=Inches(8.2))
rect(s, Inches(9.0), Inches(1.55), Inches(3.8), Inches(4.8), LIGHT)
text(s, Inches(9.25), Inches(1.8), Inches(3.4), Inches(0.6), "净效应", size=18, color=NAVY, bold=True)
text(s, Inches(9.25), Inches(2.45), Inches(3.4), Inches(3.8), [
    [("2,859 → 2,809", dict(size=20, color=INK, bold=True)), (" 行", dict(size=14, color=SUB))],
    [("-50", dict(size=14, color=RED, bold=True)), (" 重复行", dict(size=14, color=SUB))],
    [("", dict(size=6, color=SUB))],
    [("$265,880 → $183,483", dict(size=17, color=INK, bold=True))],
    [("+44.9%", dict(size=16, color=RED, bold=True)), (" 营收虚高移除", dict(size=14, color=SUB))],
    [("", dict(size=6, color=SUB))],
    [("18/18", dict(size=20, color=NAVY, bold=True)), (" 校验通过", dict(size=14, color=SUB))],
])

# 6 — Baseline retest -----------------------------------------------------
s = slide()
title_bar(s, "基线重测：清洗消除失真而非制造跳跃")
rect(s, Inches(0.55), Inches(1.5), Inches(6.1), Inches(4.9), LIGHT)
text(s, Inches(0.85), Inches(1.7), Inches(5.5), Inches(0.5), "MAPE（脏 → 清洗）", size=16, color=NAVY, bold=True)
table_data = [
    ["persistence", "252.5% → 79.9%"],
    ["weekday_naive", "227.1% → 57.3%"],
    ["random_forest", "303.7% → 65.3%"],
]
yy = 2.3
for m, v in table_data:
    text(s, Inches(0.85), Inches(yy), Inches(2.7), Inches(0.5), m, size=15, color=INK, bold=True)
    text(s, Inches(3.0), Inches(yy), Inches(3.3), Inches(0.5), v, size=15, color=RED)
    yy += 0.95
text(s, Inches(0.85), Inches(5.3), Inches(5.6), Inches(1.0),
     "三个模型误差均降 3–5 倍，回落到日营收固有噪声地板（~55–65%）。",
     size=13, color=SUB)
pic(s, FIG / "fig5_retest.png", Inches(6.9), Inches(1.55), w=Inches(5.9))

# 7 — Conclusion ----------------------------------------------------------
s = slide()
rect(s, 0, 0, SW, SH, NAVY)
rect(s, 0, Inches(4.75), SW, Inches(0.06), AMBER)
text(s, Inches(0.9), Inches(1.2), Inches(11.5), Inches(1.2),
     "结论与展望", size=34, color=WHITE, bold=True, font="Segoe UI Semibold")
bullets(s, Inches(0.9), Inches(2.6), Inches(11.5), Inches(2.0), [
    ("可审计", " — 每步修复记录在 audit_log.csv 与 change_log.md"),
    ("可复现", " — 唯一随机源（product_id）固定种子 42，一条命令重放"),
    ("可信", " — 18/18 校验通过，基线误差降 3–5 倍"),
], size=16)
text(s, Inches(0.9), Inches(5.1), Inches(11.5), Inches(1.4),
     "下一步：挑战 03（数据 → 信号）—— 以这份可信数据为地基，做时间序列模式建模与未来预测。",
     size=20, color=PALE)

prs.save(str(OUT))
print("PPTX written to", OUT)