"""Markdown calculator for merchandisers: python src/build_workbook.py -> markdown_calculator.xlsx
Blue = input, yellow = change me, black = formula."""
import sys
from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

R = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R / "src"))
F, B, BL = Font(name="Arial"), Font(name="Arial", bold=True), Font(name="Arial", color="0000FF")
Y = PatternFill("solid", fgColor="FFFF00")
wb = Workbook()

# ---------------------------------------------------------------- 1. single-SKU calculator
ws = wb.active; ws.title = "Markdown calculator"
ws["A1"] = "What discount should this product take?"; ws["A1"].font = B
ws["A2"] = "Change the yellow cells. The grid below shows gross profit at each discount; the answer is the best row."
rows = [("Full price", 2.05, '#,##0.00'), ("Cost per unit (% of price)", 0.55, "0%"),
        ("Salvage value of leftover (% of price)", 0.20, "0%"), ("Units sold per week at full price", 689, "#,##0"),
        ("Stock on hand", 9228, "#,##0"), ("Weeks left in season", 8, "0"),
        ("Price elasticity (from results/elasticities.csv)", -3.74, "0.00")]
for i, (lab, v, fmt) in enumerate(rows, 4):
    ws.cell(i, 1, lab).font = F
    c = ws.cell(i, 2, v); c.font = BL; c.fill = Y; c.number_format = fmt
ws["A12"] = "Weeks of cover at full price"; ws["B12"] = "=IF(B7=0,0,B8/B7)"; ws["B12"].number_format = "0.0"
hdr = ["Discount", "Price", "Units/week", "Units sold", "Leftover", "Gross profit"]
ws.append([]); ws.append(hdr)
for c in ws[14]:
    c.font = B; c.alignment = Alignment(wrap_text=True)
first = 15
for k in range(13):                                   # 0% to 60% in 5% steps
    i = first + k
    ws.cell(i, 1, k * 0.05).number_format = "0%"
    ws.cell(i, 2, f"=$B$4*(1-A{i})").number_format = "#,##0.00"
    ws.cell(i, 3, f"=$B$7*(1-A{i})^$B$10").number_format = "#,##0"
    ws.cell(i, 4, f"=MIN($B$8,C{i}*$B$9)").number_format = "#,##0"
    ws.cell(i, 5, f"=$B$8-D{i}").number_format = "#,##0"
    ws.cell(i, 6, f"=D{i}*(B{i}-$B$4*$B$5)+E{i}*($B$4*$B$6-$B$4*$B$5)").number_format = "#,##0.00"
last = first + 12
ws["A29"] = "Best discount"; ws["B29"] = f"=INDEX(A{first}:A{last},MATCH(MAX(F{first}:F{last}),F{first}:F{last},0))"
ws["B29"].number_format = "0%"; ws["A29"].font = B
ws["A30"] = "Gross profit at that discount"; ws["B30"] = f"=MAX(F{first}:F{last})"; ws["B30"].number_format = "#,##0.00"
ws["A31"] = "Gain vs no markdown"; ws["B31"] = f"=B30-F{first}"; ws["B31"].number_format = "#,##0.00"
ws["A33"] = "Cost and salvage are assumptions, not data: this dataset has no cost figures. Elasticity is measured, and is an association, not an experiment."
for col, w in zip("ABCDEF", [44, 14, 13, 13, 12, 14]):
    ws.column_dimensions[col].width = w

# ---------------------------------------------------------------- 2. this week's markdown list
ml = pd.read_csv(R / "results" / "markdown_list.csv").head(60)
ws2 = wb.create_sheet("This week's list")
ws2.append(["Top 60 products by gross profit gained if marked down (from results/markdown_list.csv)"])
ws2["A1"].font = B
ws2.append([])
cols = ["StockCode", "desc", "base_price", "elasticity", "return_rate", "stock", "ros_units_per_week",
        "weeks_of_cover", "recommended_markdown_pct", "str_no_markdown_pct", "str_with_markdown_pct", "gross_profit_gain"]
names = ["SKU", "Description", "Full price", "Elasticity", "Return rate", "Stock", "Units/week", "Weeks of cover",
         "Recommended markdown", "Sell-through if no markdown", "Sell-through with markdown", "Gross profit gained"]
ws2.append(names)
for c in ws2[3]:
    c.font = B; c.alignment = Alignment(wrap_text=True)
for i, r in enumerate(ml[cols].itertuples(index=False), 4):
    for j, v in enumerate(r, 1):
        cell = ws2.cell(i, j, v); cell.font = BL
        if j in (5, 9, 10, 11):
            cell.number_format = "0.0%" if j == 5 else "0.0"
ws2.freeze_panes = "A4"
for j, w in enumerate([12, 36, 11, 11, 11, 10, 11, 12, 13, 14, 14, 14], 1):
    ws2.column_dimensions[get_column_letter(j)].width = w

ws3 = wb.create_sheet("Notes")
for line in ["Built for Snitch's PS-II internship by Pavitra Seth.",
             "Data: 541,909 real transaction lines from a public online-retail dataset (Dec 2010 - Dec 2011), used as a stand-in for Snitch's own sales.",
             "Elasticity is estimated per SKU from real week-to-week price variation and validated on weeks the model never saw.",
             "Blue = input or data; yellow = change me; black = formula."]:
    ws3.append([line])
ws3.column_dimensions["A"].width = 125
for wsx in wb.worksheets:
    for row in wsx.iter_rows():
        for c in row:
            if c.font != BL and not c.font.bold:
                c.font = F
wb.save(R / "markdown_calculator.xlsx"); print("saved markdown_calculator.xlsx")
