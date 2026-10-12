"""Generate reports/executive_summary.pdf via reportlab (with CJK fonts)."""
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
MUTED = colors.HexColor("#5b6472")

body = ParagraphStyle("body", fontName="Deng", fontSize=10, leading=15,
                      textColor=colors.HexColor("#1a2332"))
h2 = ParagraphStyle("h2", fontName="Hei", fontSize=13, leading=18, textColor=ACCENT,
                    spaceBefore=10, spaceAfter=4)
cap = ParagraphStyle("cap", fontName="Deng", fontSize=8, leading=11, textColor=MUTED,
                     alignment=1, spaceAfter=8)

story = []

hero_inner = [
    Paragraph("挑战 03 · 数据 → 信号", ParagraphStyle("t1", fontName="Hei", fontSize=18,
                                                 leading=24, textColor=colors.white)),
    Paragraph("把干净的数据转化为启发性的预测信号 —— 季节性 · 周期 · 节假日",
              ParagraphStyle("t2", fontName="Deng", fontSize=11, leading=16,
                             textColor=colors.HexColor("#d6eaf8"))),
]
hero = Table([[hero_inner]], colWidths=[170 * mm])
hero.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, -1), ACCENT),
    ("LEFTPADDING", (0, 0), (-1, -1), 12), ("RIGHTPADDING", (0, 0), (-1, -1), 12),
    ("TOPPADDING", (0, 0), (-1, -1), 10), ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
]))
story.append(hero)
story.append(Spacer(1, 8))

story.append(Paragraph("1  信号结论", h2))
story.append(Paragraph(
    "对 5 年、3 门店 × 4 品类、共 21,912 条日销售做信号工程。无监督周期图自动发现两个主导周期 "
    "<b>7 天（周）</b> 与 <b>~365 天（年）</b>；节假日当日销售平均 <b>+12.5%</b>；"
    "价格-数量弹性≈0，说明需求由日历驱动而非价格。", body))
story.append(Spacer(1, 6))

story.append(Paragraph("2  季节性与外部因子", h2))
story.append(Image(str(FIG / "fig4_annual_seasonality.png"), width=165 * mm, height=62 * mm))
story.append(Paragraph("年周期：Q4 节假日峰，Bakery 最陡峭", cap))
story.append(Image(str(FIG / "fig7_holiday_uplift.png"), width=80 * mm, height=48 * mm))
story.append(Paragraph("节假日 vs 平日营收分布", cap))

story.append(Paragraph("3  预测：SARIMA → SARIMAX", h2))
story.append(Paragraph(
    "训练 2018–2021，全盲测 2022。SARIMAX 在周季节之上叠加 <b>is_holiday + 2 对年度傅里叶</b>外生因子，"
    "捕捉周模型无法触及的节假日冲击。", body))
tbl = Table([
    ["模型", "MAE ($)", "RMSE ($)", "MAPE (%)"],
    ["persistence", "1,936", "2,324", "24.7"],
    ["seasonal-naive", "1,801", "2,259", "20.5"],
    ["SARIMA（仅周）", "1,357", "1,743", "15.1"],
    ["SARIMAX（+假日/年度）", "910", "1,286", "10.5"],
], colWidths=[75 * mm, 30 * mm, 30 * mm, 30 * mm])
tbl.setStyle(TableStyle([
    ("FONTNAME", (0, 0), (-1, 0), "Hei"),
    ("FONTNAME", (0, 1), (-1, -1), "Deng"),
    ("FONTNAME", (0, 4), (-1, 4), "DengBold"),
    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
    ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
    ("BACKGROUND", (0, 4), (-1, 4), colors.HexColor("#ebf5fb")),
    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
    ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
    ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
]))
story.append(tbl)
story.append(Spacer(1, 8))
story.append(Image(str(FIG / "fig10_forecast_total.png"), width=165 * mm, height=70 * mm))
story.append(Paragraph("2022 全盲测：SARIMAX 预测 vs 实际（95% CI）", cap))

story.append(Paragraph("4  分层结果与业务启示", h2))
story.append(Image(str(FIG / "fig11_hierarchy_mape.png"), width=165 * mm, height=70 * mm))
story.append(Paragraph("细分 MAPE：朴素→SARIMA→SARIMAX", cap))
story.append(Paragraph(
    "所有 7 个细分上 SARIMAX 一致优于 SARIMA，其中 <b>Bakery 从 78% 降至 30%</b>——其需求由节假峰驱动，"
    "显式外部因子精准捕捉。启示：节假日是最强可预测信号，品类应按季节敏感度分层建模。", body))

story.append(Paragraph("5  可复现性", h2))
story.append(Paragraph(
    "全流程确定性、零远程依赖：节假日日历手写、预测模型无随机种子。"
    "<b>python scripts/run_eda.py && python scripts/run_forecast.py</b> 一键重放，"
    "指标落地于 reports/*.json 可追溯。", body))

doc = SimpleDocTemplate(str(OUT), pagesize=A4, topMargin=14 * mm, bottomMargin=14 * mm,
                        leftMargin=18 * mm, rightMargin=18 * mm)
doc.build(story)
print("PDF written to", OUT)