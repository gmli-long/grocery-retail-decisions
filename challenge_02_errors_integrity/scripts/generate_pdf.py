"""Generate reports/executive_summary.pdf for Challenge 02."""
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Image,
                                Table, TableStyle)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

BASE = Path(__file__).resolve().parent.parent
FIG = BASE / "reports" / "figures"
OUT = BASE / "reports" / "executive_summary.pdf"

pdfmetrics.registerFont(TTFont("Hei", "C:/Windows/Fonts/simhei.ttf"))
pdfmetrics.registerFont(TTFont("Deng", "C:/Windows/Fonts/Deng.ttf"))
pdfmetrics.registerFont(TTFont("DengBold", "C:/Windows/Fonts/Dengb.ttf"))

ACCENT = colors.HexColor("#1b4f72")
RED = colors.HexColor("#c0392b")
AMBER = colors.HexColor("#f0a32c")
MUTED = colors.HexColor("#5b6472")

body = ParagraphStyle("body", fontName="Deng", fontSize=10.5, leading=16,
                      textColor=colors.HexColor("#1a2332"))
h2 = ParagraphStyle("h2", fontName="Hei", fontSize=13, leading=18, textColor=ACCENT,
                    spaceBefore=10, spaceAfter=4)
cap = ParagraphStyle("cap", fontName="Deng", fontSize=8.5, leading=12, textColor=MUTED,
                     alignment=1, spaceAfter=8)

story = []

hero = Table([[Paragraph("挑战 02 · 执行摘要", ParagraphStyle(
    "t1", fontName="Hei", fontSize=18, leading=24, textColor=colors.white)),
    Paragraph("从数据混乱到数据信心 —— 审计 · 修复 · 验证一条可信数据流水线",
              ParagraphStyle("t2", fontName="Deng", fontSize=11, leading=16,
                             textColor=colors.HexColor("#d6eaf8")))]], colWidths=[170 * mm])
hero.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, -1), ACCENT),
    ("LEFTPADDING", (0, 0), (-1, -1), 12), ("RIGHTPADDING", (0, 0), (-1, -1), 12),
    ("TOPPADDING", (0, 0), (-1, -1), 10), ("BOTTOMPADDING", (0, 0), (-1, -1), 10)]))
story.append(hero)
story.append(Spacer(1, 8))

story.append(Paragraph("1  概览", h2))
story.append(Paragraph(
    "对一套结构化但充满噪音的杂货零售数据库做系统审计，共发现 <b>9 类注入错误</b>。"
    "修复遵循「精确还原优先」原则，其中 4 项（qty / unit_price / txn_date / store_id）"
    "从业务不变量<b>精确反推</b>，仅 product_id 因无信号而做种子化比例抽样。"
    "清洗后 <b>18/18 项完整性校验通过</b>，sales 从 2,859 行收敛到 2,809 行，"
    "总营收从 <font color='#c0392b'>$265,880</font> 修正为 $183,483（−31.0%，移除 +44.9% 虚高）。",
    body))
story.append(Spacer(1, 6))

story.append(Paragraph("2  审计发现（9 类错误）", h2))
tbl = Table([
    ["#", "类别", "表·列", "计数"],
    ["1", "缺失 txn_date", "sales.txn_date", "29"],
    ["2", "缺失 qty", "sales.qty", "57"],
    ["3", "缺失 unit_price", "sales.unit_price", "56"],
    ["4", "重复 txn_id（47 同/3 冲突）", "sales.txn_id", "50 组"],
    ["5", "外键孤儿 store_id=9999", "sales.store_id", "14"],
    ["6", "外键孤儿 product_id=9999", "sales.product_id", "29"],
    ["7", "数量离群 1000–4000", "sales.qty", "29"],
    ["8", "金额不一致 ≠ qty×price", "sales.line_amount", "43"],
    ["9", "类别命名漂移", "categories.name", "2"],
], colWidths=[10 * mm, 78 * mm, 50 * mm, 22 * mm])
tbl.setStyle(TableStyle([
    ("FONTNAME", (0, 0), (-1, 0), "Hei"), ("FONTNAME", (0, 1), (-1, -1), "Deng"),
    ("FONTSIZE", (0, 0), (-1, -1), 9),
    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef3f8")),
    ("TEXTCOLOR", (0, 0), (-1, 0), ACCENT),
    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e6e9ef")),
    ("ALIGN", (0, 0), (0, -1), "CENTER"), ("ALIGN", (3, 0), (3, -1), "CENTER"),
]))
story.append(tbl)
story.append(Spacer(1, 6))

story.append(Paragraph("3  修复策略：精确还原优先", h2))
story.append(Paragraph(
    "<b>精确还原</b>：缺失 qty / unit_price 由派生不变量 <i>line_amount = qty × unit_price</i> 反推；"
    "缺失 txn_date 由 <i>txn_id → 日期</i> 的单调阶跃结构前向填充；store_id=9999 由每日门店 1→5 "
    "连续循环还原。数量离群 ÷1000、金额 ×100 重算。"
    "<b>唯一无信号列 product_id</b> 与任何观测列均不相关，采用种子化比例抽样保持边际分布无偏。",
    body))
story.append(Spacer(1, 4))
for f, w in [("fig3_amount_ratio.png", 85), ("fig2_qty_spikes.png", 85)]:
    story.append(Image(str(FIG / f), width=w * mm, height=w * 0.49 * mm))
    story.append(Spacer(1, 3))

story.append(Paragraph("4  前后对比与验证", h2))
story.append(Image(str(FIG / "fig4_daily_revenue.png"), width=165 * mm, height=60 * mm))
story.append(Paragraph("每日营收：清洗把虚高 43.6% 的曲线拉回真实水位，且不扭曲任何一日的形状", cap))

story.append(Paragraph("5  基线重测：脏数据 vs 清洗后", h2))
tbl2 = Table([
    ["模型", "MAPE（脏）", "MAPE（清洗）", "下降（×）"],
    ["persistence", "252.50%", "79.95%", "3.2×"],
    ["weekday_naive", "227.12%", "57.29%", "4.0×"],
    ["random_forest", "303.71%", "65.32%", "4.7×"],
], colWidths=[45 * mm, 40 * mm, 42 * mm, 33 * mm])
tbl2.setStyle(TableStyle([
    ("FONTNAME", (0, 0), (-1, 0), "Hei"), ("FONTNAME", (0, 1), (-1, -1), "Deng"),
    ("FONTSIZE", (0, 0), (-1, -1), 9.5),
    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef3f8")),
    ("TEXTCOLOR", (0, 0), (-1, 0), ACCENT),
    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e6e9ef")),
    ("ALIGN", (1, 0), (-1, -1), "CENTER"),
    ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#fef5e7")),
]))
story.append(tbl2)
story.append(Spacer(1, 4))
story.append(Image(str(FIG / "fig5_retest.png"), width=160 * mm, height=62 * mm))
story.append(Paragraph("测试窗口（门店 5）：脏数据训练的模型被 ×100 尖峰与重复计费带偏，清洗后误差回落到真实业务噪声地板", cap))

story.append(Paragraph("6  结论与下一步", h2))
story.append(Paragraph(
    "· 可审计：9 类错误全量枚举，每步修复记录在 <i>audit_log.csv</i> 与 <i>change_log.md</i>；"
    "· 可复现：唯一随机源（product_id 抽样）固定种子 42，一条命令重放全链路；"
    "· 可信：18/18 校验通过、基线误差降低 3–5 倍，证明清洗消除失真而非制造跳跃。"
    "<b>挑战 03 衔接</b>：这份可信数据将作为时间序列预测（数据→信号）的建模地基。",
    body))

doc = SimpleDocTemplate(str(OUT), pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm,
                        topMargin=18 * mm, bottomMargin=16 * mm, title="挑战 02 执行摘要")
doc.build(story)
print("PDF written to", OUT)