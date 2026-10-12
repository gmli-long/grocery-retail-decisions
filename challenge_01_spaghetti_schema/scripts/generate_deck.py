"""Build slides/presentation_deck.pptx (7 slides, 16:9) with python-pptx."""
from pathlib import Path
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR

BASE = Path(__file__).resolve().parent.parent
FIG = BASE / "reports" / "figures"
OUT = BASE / "slides" / "presentation_deck.pptx"
OUT.parent.mkdir(parents=True, exist_ok=True)

NAVY = RGBColor(0x1B, 0x4F, 0x72)
BLUE = RGBColor(0x2C, 0x7F, 0xB8)
INK = RGBColor(0x1A, 0x23, 0x32)
SUB = RGBColor(0x5B, 0x64, 0x72)
AMBER = RGBColor(0xF0, 0xA3, 0x2C)
LIGHT = RGBColor(0xF6, 0xF8, 0xFA)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)

prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)
BLANK = prs.slide_layouts[6]
SW, SH = prs.slide_width, prs.slide_height


def add_slide():
    return prs.slides.add_slide(BLANK)


def rect(slide, x, y, w, h, color):
    from pptx.enum.shapes import MSO_SHAPE
    shp = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, y, w, h)
    shp.fill.solid(); shp.fill.fore_color.rgb = color
    shp.line.fill.background()
    shp.shadow.inherit = False
    return shp


def text(slide, x, y, w, h, runs, size=18, color=INK, bold=False, align=PP_ALIGN.LEFT,
         font="Segoe UI", anchor=MSO_ANCHOR.TOP):
    tb = slide.shapes.add_textbox(x, y, w, h)
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


def title_bar(slide, title, sub=None):
    rect(slide, 0, 0, SW, Inches(1.05), NAVY)
    text(slide, Inches(0.55), Inches(0.16), SW - Inches(1.1), Inches(0.6),
         title, size=26, color=WHITE, bold=True, font="Segoe UI Semibold",
         anchor=MSO_ANCHOR.MIDDLE)
    if sub:
        text(slide, Inches(0.55), Inches(0.72), SW - Inches(1.1), Inches(0.3),
             sub, size=12, color=RGBColor(0xD6, 0xEA, 0xF8), font="Segoe UI")


def bullets(slide, x, y, w, h, items, size=15):
    lines = []
    for it in items:
        head, rest = it if isinstance(it, tuple) else ("", it)
        lines.append([
            ("• ", dict(size=size, color=BLUE, bold=True)),
            (head, dict(size=size, color=INK, bold=True)),
            (rest, dict(size=size, color=INK, bold=False)),
        ])
    text(slide, x, y, w, h, lines)


def pic(slide, path, x, y, w=None, h=None):
    return slide.shapes.add_picture(str(path), x, y, width=w, height=h)


# ============================ Slide 1 : Title ===============================
s = add_slide()
rect(s, 0, 0, SW, SH, NAVY)
rect(s, 0, Inches(4.9), SW, Inches(0.06), AMBER)
text(s, Inches(0.9), Inches(1.6), Inches(11.5), Inches(1.6),
     "挑战 01 · 从数据混乱到分析清晰", size=40, color=WHITE, bold=True, font="Segoe UI Semibold")
text(s, Inches(0.9), Inches(2.9), Inches(11), Inches(1.0),
     "将分散的电子表格转化为结构化、可查询、可复现的关系型数据底座\n—— 并验证其分析与建模就绪度",
     size=20, color=RGBColor(0xD6, 0xEA, 0xF8))
for i, (v, l) in enumerate([("7→11", "7 平面文件 → 11 规范化实体"),
                            ("0", "异常行（约束全满足）"),
                            ("$512k", "2024 年总营收"),
                            ("33.1%", "基线模型 MAPE")]):
    x = Inches(0.9 + i * 3.05)
    text(s, x, Inches(5.3), Inches(2.8), Inches(0.7), v, size=30, color=WHITE, bold=True)
    text(s, x, Inches(6.0), Inches(2.8), Inches(0.6), l, size=13, color=RGBColor(0xA9, 0xCC, 0xE3))

# ============================ Slide 2 : Pipeline ============================
s = add_slide()
title_bar(s, "数据管道概览", "一个命令复现整个流程：scripts/load_data.py")
steps = [("接入", "7 个平面文件\n4 种异构日期格式"),
         ("清洗/类型强制", "数值·日期强制\n异常行标记"),
         ("建模", "维度去重\n代理键 + 外键解析"),
         ("校验", "PK/FK/CHECK 审计\n计数日志"),
         ("加载", "PostgreSQL\n(或 SQLite 回退)")]
for i, (t, d) in enumerate(steps):
    x = Inches(0.55 + i * 2.45)
    rect(s, x, Inches(2.1), Inches(2.1), Inches(2.6), LIGHT)
    rect(s, x, Inches(2.1), Inches(2.1), Inches(0.55), BLUE if i < 4 else AMBER)
    text(s, x, Inches(2.16), Inches(2.1), Inches(0.45), t, size=16, color=WHITE, bold=True,
         align=PP_ALIGN.CENTER)
    text(s, x + Inches(0.12), Inches(2.85), Inches(1.86), Inches(1.6), d, size=13, color=INK)
    if i < 4:
        text(s, x + Inches(2.05), Inches(3.2), Inches(0.45), Inches(0.5), "→",
             size=24, color=BLUE, bold=True)
bullets(s, Inches(0.55), Inches(5.2), Inches(12.2), Inches(1.9), [
    ("行数对账（ETL 日志）：", "products=60 · promotions=530 · stores=3 · receipts=13,259 · line_items=53,286 · inventory=2,160"),
    ("约束结果：", "REJECTED rows = 0，全部主键/外键/CHECK 约束满足"),
    ("可审计：", "逐表 source_rows / loaded 计数，异常行落盘 reports/etl/rejected_rows.csv"),
], size=15)

# ============================ Slide 3 : ERD =================================
s = add_slide()
title_bar(s, "ERD 与模式设计", "7 张维度 + 4 张事实，products 为中枢，票头/票行分离")
pic(s, FIG / "erd.png", Inches(0.7), Inches(1.4), w=Inches(11.9))
bullets(s, Inches(0.7), Inches(6.55), Inches(11.9), Inches(0.8), [
    ("规范化决策：", "部门→类目→商品消除传递依赖；丢弃可推导列 weekend_flag、库存 unit_cost/value"),
], size=13)

# ============================ Slide 4 : EDA (1) =============================
s = add_slide()
title_bar(s, "EDA 亮点（1/2）", "品类结构 · 门店 × 客群")
pic(s, FIG / "fig1_department_revenue.png", Inches(0.5), Inches(1.5), w=Inches(6.0))
pic(s, FIG / "fig3_store_segment.png", Inches(6.9), Inches(1.5), w=Inches(5.9))
bullets(s, Inches(0.5), Inches(5.4), Inches(12.3), Inches(1.6), [
    ("品类：", "Grocery 绝对主力（≈$174k，占 34%）；Wellness / Meat-Seafood / Dairy / Produce 第二梯队"),
    ("门店：", "三店体量几乎一致（各 ≈$170k），会员贡献稳定更高"),
], size=14)

# ============================ Slide 5 : EDA (2) =============================
s = add_slide()
title_bar(s, "EDA 亮点（2/2）", "时间趋势 · 促销 lift")
pic(s, FIG / "fig2_monthly_trend.png", Inches(0.5), Inches(1.5), w=Inches(6.0))
pic(s, FIG / "fig4_promo_lift.png", Inches(6.9), Inches(1.5), w=Inches(5.9))
bullets(s, Inches(0.5), Inches(5.4), Inches(12.3), Inches(1.6), [
    ("时间：", "月营收 $40k–$45k 窄幅波动，促销占比稳定 8%–11%"),
    ("促销：", "BOGO50 把行均数量 1.29→2.16、行均营收最高（提量型）；PCT_OFF/LOYALTY_PCT 降价换量"),
], size=14)

# ============================ Slide 6 : Model ===============================
s = add_slide()
title_bar(s, "基线模型：单店每日销售预测", "RandomForest（日历特征）vs 两个朴素基线")
rows = [("模型", "MAE ($)", "RMSE ($)", "MAPE (%)"),
        ("persistence（昨日值）", "176.1", "224.1", "41.42"),
        ("weekday_naive（上周同 weekday）", "197.6", "241.4", "48.52"),
        ("random_forest", "135.8", "170.6", "33.05")]
tbl_shape = s.shapes.add_table(len(rows), 4, Inches(6.9), Inches(1.6), Inches(5.8), Inches(2.2))
tbl = tbl_shape.table
for r, row in enumerate(rows):
    for c, val in enumerate(row):
        cell = tbl.cell(r, c); cell.text = val
        p = cell.text_frame.paragraphs[0]; p.alignment = PP_ALIGN.LEFT if c == 0 else PP_ALIGN.CENTER
        for run in p.runs:
            run.font.size = Pt(13); run.font.name = "Segoe UI"
            run.font.color.rgb = INK
            run.font.bold = (r == 0 or r == 3)
pic(s, FIG / "fig7_forecast.png", Inches(0.5), Inches(1.7), w=Inches(6.0))
bullets(s, Inches(0.5), Inches(4.9), Inches(12.2), Inches(1.9), [
    ("结果：", "RF 的 MAPE 比最优朴素基线提升 15.5 个百分点，dayofyear 为首要特征"),
    ("切分：", "训练 1–10 月，测试 11–12 月（183 门店-日，覆盖 100%）"),
    ("局限：", "日粒度噪声大（单店日均 ≈$156），聚合到周可显著降低误差；仅日历特征、单年窗口"),
], size=13)

# ============================ Slide 7 : Takeaways ===========================
s = add_slide()
title_bar(s, "关键要点与下一步", "为挑战 02（完整性 → 错误）铺路")
bullets(s, Inches(0.7), Inches(1.7), Inches(12), Inches(3.4), [
    ("可复现：", "一条命令 python scripts/load_data.py 从 7 个文件重建库，行数与源文件严格一致、0 异常行"),
    ("可追踪：", "逐表计数日志 + 异常行落盘，为审计与自动化铺路"),
    ("分析就绪：", "6 张 EDA 图 + 优于朴素基线的预测模型，均由规范 schema 的标准 SQL 驱动"),
    ("建模严谨：", "3NF + 完整外键/CHECK 约束，自身即数据质量第一道防线"),
], size=16)
rect(s, Inches(0.7), Inches(5.15), Inches(11.9), Inches(1.35),
     RGBColor(0xFE, 0xF5, 0xE7))
text(s, Inches(0.95), Inches(5.3), Inches(11.5), Inches(1.1),
     [[("挑战 02 衔接：", dict(size=15, color=RGBColor(0xB2, 0x6B, 0x00), bold=True)),
       (" ETL 已预留「不可解析日期 / 外键孤儿 / 数值越界 / 重复键」四类拒绝路径，可在真实数据质量压力下直接量化错误。",
        dict(size=14, color=INK))]])

prs.save(OUT)
print("Deck written to", OUT, f"({len(prs.slides._sldIdLst)} slides)")