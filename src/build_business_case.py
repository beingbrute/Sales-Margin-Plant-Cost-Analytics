"""
Build excel/business_case.xlsx from the exported reporting files (run src/export_reporting.py first).

Sheets:
  Read me         the questions, how to use the model, and its limits
  Assumptions     every input in one place (blue = from the data, yellow = assumption to agree with the business)
  WH Supply       North water heaters last winter: what Haridwar could not supply, what it cost, spare capacity
  Business Case   P2: three options for next winter, annual cost, ranking, sensitivity to the carrying rate
  Copper What-If  P1: wire gross margin % for copper and price changes, and the price rise needed to hold margin
  Data_*          values exported from PostgreSQL (do not edit)

Every result is an Excel formula, so changing an assumption updates the model.

    python src/build_business_case.py
"""
import csv
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

ROOT = Path(__file__).resolve().parents[1]
REP = ROOT / "reporting"
OUT = ROOT / "excel" / "business_case.xlsx"

BLUE = Font(color="0000FF")
BOLD = Font(bold=True)
TITLE = Font(bold=True, size=14)
NOTE = Font(italic=True, color="595959")
YELLOW = PatternFill("solid", fgColor="FFFF00")
HEAD = PatternFill("solid", fgColor="DDE2E8")
BEST = PatternFill("solid", fgColor="C6EFCE")
INR = '#,##0;(#,##0);"-"'
LAKH = '#,##0.0;(#,##0.0);"-"'
PCT = '0.0%;(0.0%);"-"'
NUM = '#,##0'
NUM4 = '0.0000'


def read(name):
    with open(REP / f"{name}.csv", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def head(ws, row, values, col=1):
    for i, v in enumerate(values):
        c = ws.cell(row=row, column=col + i, value=v)
        c.font, c.fill = BOLD, HEAD
        c.alignment = Alignment(wrap_text=True, vertical="top")


def widths(ws, w):
    for i, x in enumerate(w, start=1):
        ws.column_dimensions[get_column_letter(i)].width = x


def num(v):
    return float(v) if v not in ("", None) else 0.0


wb = Workbook()

# ------------------------------------------------------------------ data sheets
wh = read("wh_supply_monthly")
dw = wb.active
dw.title = "Data_WH"
wh_cols = ["month", "north_ordered", "north_from_haridwar", "north_from_hosur", "north_short", "east_from_haridwar",
           "north_margin_per_unit", "north_std_cost_per_unit", "haridwar_hours_used", "hours_per_unit",
           "available_hours", "downtime_days", "freight_haridwar_to_north", "freight_hosur_to_north"]
head(dw, 1, wh_cols)
for i, r in enumerate(wh, start=2):
    dw.cell(row=i, column=1, value=r["month"])
    for j, k in enumerate(wh_cols[1:], start=2):
        dw.cell(row=i, column=j, value=num(r[k]))
dw.cell(row=15, column=1, value="Source: rpt.wh_supply_monthly (water heaters, Haridwar line WH-L1, FY 2025-26)").font = NOTE
widths(dw, [10] + [14] * 13)

wires = read("wire_cost_monthly")
dc = wb.create_sheet("Data_Wires")
w_cols = ["month", "units", "net_sales", "cost_at_standard", "copper_cost", "copper_per_kg"]
head(dc, 1, w_cols)
for i, r in enumerate(wires, start=2):
    dc.cell(row=i, column=1, value=r["month"])
    for j, k in enumerate(w_cols[1:], start=2):
        dc.cell(row=i, column=j, value=num(r[k]))
dc.cell(row=15, column=1, value="Source: rpt.wire_cost_monthly (wires, invoices only)").font = NOTE
widths(dc, [10, 12, 16, 16, 16, 14])

# ------------------------------------------------------------------ assumptions
a = wb.create_sheet("Assumptions", 0)
a["A1"] = "Assumptions"
a["A1"].font = TITLE
a["A2"] = "Blue = from the data. Yellow = assumption to agree with the business before using the result."
a["A2"].font = NOTE
head(a, 4, ["Input", "Value", "Unit", "Source / note"])
ASSUME = [  # (name, value or formula, unit, note, yellow?)
    ("Working days per month", 26, "days", "Plant calendar (6-day week)", False),
    ("Available machine hours per month, WH-L1", "=Data_WH!K2", "hours", "pp.plant_capacity", False),
    ("Hours per water heater, WH-L1", "=AVERAGE(Data_WH!J2:J13)", "hours", "Machine hours / units made", False),
    ("Maximum planned utilisation", 0.85, "share", "Leave room for changeovers and maintenance", True),
    ("Downtime days per month, Oct–Jan last winter", "=Data_WH!L8", "days", "pp.plant_capacity", False),
    ("Standard cost per water heater (North)", "=AVERAGE(Data_WH!H8:H11)", "INR", "Oct–Jan average", False),
    ("Margin per water heater (North)", "=AVERAGE(Data_WH!G8:G11)", "INR", "Net price - standard cost, Oct–Jan", False),
    ("Inventory carrying rate", 0.15, "per year", "Cost of money tied up in stock plus insurance and losses", True),
    ("Months pre-built stock is held", 4, "months", "Built Jun–Sep, sold Oct–Jan", True),
    ("Warehouse cost per unit per month", 25, "INR", "Extra space at the North warehouse", True),
    ("Overhaul cost of WH-L1", 25000000, "INR", "One-off; removes the winter downtime", True),
    ("Overhaul life", 5, "years", "Spread the cost over this many years", True),
    ("Extra maintenance after overhaul", 4000000, "INR per year", "Preventive maintenance contract", True),
]
for i, (name, val, unit, note, yellow) in enumerate(ASSUME, start=5):
    a.cell(row=i, column=1, value=name)
    c = a.cell(row=i, column=2, value=val)
    c.font = BLUE
    if yellow:
        c.fill = YELLOW
    c.number_format = PCT if unit in ("share", "per year") else (NUM4 if "Hours per" in name else INR)
    a.cell(row=i, column=3, value=unit)
    a.cell(row=i, column=4, value=note)
widths(a, [44, 16, 14, 60])
A = {name: f"Assumptions!$B${i}" for i, (name, *_rest) in enumerate(ASSUME, start=5)}
DAYS, HOURS, HPU, UTIL, DOWN = (A["Working days per month"], A["Available machine hours per month, WH-L1"],
                                A["Hours per water heater, WH-L1"], A["Maximum planned utilisation"],
                                A["Downtime days per month, Oct–Jan last winter"])
STD, MARGIN, CARRY, HELD, WHC = (A["Standard cost per water heater (North)"], A["Margin per water heater (North)"],
                                 A["Inventory carrying rate"], A["Months pre-built stock is held"],
                                 A["Warehouse cost per unit per month"])
CAPEX, LIFE, MAINT = A["Overhaul cost of WH-L1"], A["Overhaul life"], A["Extra maintenance after overhaul"]

# ------------------------------------------------------------------ WH Supply
s = wb.create_sheet("WH Supply", 1)
s["A1"] = "North water heaters last winter: what Haridwar could not supply, and what it cost"
s["A1"].font = TITLE
s["A2"] = "Haridwar (WH-L1) normally supplies the North. Oct–Jan it lost 9 working days a month to downtime; Hosur covered part and the rest was not shipped."
s["A2"].font = NOTE
cols = ["Month", "North ordered", "From Haridwar", "From Hosur", "Not shipped", "Not supplied by Haridwar",
        "Extra freight (INR)", "Margin lost (INR)", "Spare units at Haridwar (Apr–Sep)", "Units lost to downtime"]
head(s, 4, cols)
for i in range(12):
    r, d = 5 + i, 2 + i
    s.cell(row=r, column=1, value=f"=Data_WH!A{d}")
    s.cell(row=r, column=2, value=f"=Data_WH!B{d}")
    s.cell(row=r, column=3, value=f"=Data_WH!C{d}")
    s.cell(row=r, column=4, value=f"=Data_WH!D{d}")
    s.cell(row=r, column=5, value=f"=Data_WH!E{d}")
    s.cell(row=r, column=6, value=f"=D{r}+E{r}")
    s.cell(row=r, column=7, value=f"=D{r}*(Data_WH!N{d}-Data_WH!M{d})")
    s.cell(row=r, column=8, value=f"=E{r}*Data_WH!G{d}")
    if i <= 5:       # Apr-Sep: hours left below the maximum utilisation, in units
        s.cell(row=r, column=9, value=f"=MAX(0,({HOURS}*{UTIL}-Data_WH!I{d})/{HPU})")
    s.cell(row=r, column=10, value=f"=Data_WH!L{d}/{DAYS}*{HOURS}*{UTIL}/{HPU}")
    for c in range(2, 11):
        s.cell(row=r, column=c).number_format = INR
tot = 17
s.cell(row=tot, column=1, value="Total").font = BOLD
for c in range(2, 11):
    col = get_column_letter(c)
    s.cell(row=tot, column=c, value=f"=SUM({col}5:{col}16)").number_format = INR
    s.cell(row=tot, column=c).font = BOLD
s["A19"] = "Cost of last winter (extra freight + margin lost), INR"
s["F19"] = "=G17+H17"
s["F19"].number_format, s["F19"].font = INR, BOLD
s["A20"] = "Can the summer spare capacity at Haridwar cover what it could not supply in winter?"
s["F20"] = '=IF(I17>=F17,"Yes: "&TEXT(I17,"#,##0")&" spare units vs "&TEXT(F17,"#,##0")&" needed","No: short by "&TEXT(F17-I17,"#,##0")&" units")'
s["A22"] = "Spare units = (available hours x maximum utilisation - hours used) / hours per unit. Units lost to downtime = downtime days / working days x capacity at maximum utilisation."
s["A22"].font = NOTE
widths(s, [10, 12, 12, 12, 12, 14, 16, 16, 16, 14])

# ------------------------------------------------------------------ Business Case
b = wb.create_sheet("Business Case", 2)
b["A1"] = "P2: how should Orvane supply the North with water heaters next winter?"
b["A1"].font = TITLE
b["A2"] = "Annual cost of each option, built from last winter's volumes. Lower is better. Change the yellow assumptions to test the answer."
b["A2"].font = NOTE
head(b, 4, ["", "A. Status quo", "B. Pre-build at Haridwar", "C. Overhaul WH-L1 + smaller pre-build"])
rows = [
    ("What it means", "Hosur covers what it can; the rest is not shipped",
     "Use Haridwar's spare summer hours to build North stock before winter",
     "Fix the winter downtime; pre-build only what the line still cannot make"),
    ("Units Haridwar must add for the North", "='WH Supply'!F17", "='WH Supply'!F17", "='WH Supply'!F17"),
    ("Units recovered by removing downtime", 0, 0, "=MIN('WH Supply'!J17,'WH Supply'!F17)"),
    ("Units to pre-build in summer", 0, "=C6", "=D6-D7"),
    ("Pre-build fits spare summer capacity?", "n/a", "=IF(C8<='WH Supply'!I17,\"Yes\",\"No\")",
     "=IF(D8<='WH Supply'!I17,\"Yes\",\"No\")"),
    ("Extra freight from Hosur (INR)", "='WH Supply'!G17", 0, 0),
    ("Margin lost on orders not shipped (INR)", "='WH Supply'!H17", 0, 0),
    ("Cost of holding pre-built stock (INR)", 0, f"=C8*{STD}*{CARRY}*{HELD}/12", f"=D8*{STD}*{CARRY}*{HELD}/12"),
    ("Warehouse space for pre-built stock (INR)", 0, f"=C8*{WHC}*{HELD}", f"=D8*{WHC}*{HELD}"),
    ("Overhaul, spread over its life (INR)", 0, 0, f"={CAPEX}/{LIFE}"),
    ("Extra maintenance (INR)", 0, 0, f"={MAINT}"),
]
for i, (label, *vals) in enumerate(rows, start=5):
    b.cell(row=i, column=1, value=label)
    for j, v in enumerate(vals, start=2):
        c = b.cell(row=i, column=j, value=v)
        c.alignment = Alignment(wrap_text=True, vertical="top")
        if i >= 6 and i != 9:
            c.number_format = INR
b.row_dimensions[5].height = 45
b.cell(row=17, column=1, value="Annual cost (INR)").font = BOLD
for col in "BCD":
    c = b[f"{col}17"]
    c.value = f"=SUM({col}10:{col}15)"
    c.number_format, c.font = INR, BOLD
b["A18"] = "Annual cost (INR lakh)"
for col in "BCD":
    b[f"{col}18"] = f"={col}17/100000"
    b[f"{col}18"].number_format = LAKH
b["A19"] = "Saving against the status quo (INR lakh)"
for col in "CD":
    b[f"{col}19"] = f"=($B$17-{col}17)/100000"
    b[f"{col}19"].number_format = LAKH
b["A20"] = "Rank (1 = cheapest)"
for col in "BCD":
    b[f"{col}20"] = f"=RANK({col}17,$B$17:$D$17,1)"
b["A22"] = "Recommendation"
b["A22"].font = BOLD
b["B22"] = '=INDEX($B$4:$D$4,MATCH(MIN($B$17:$D$17),$B$17:$D$17,0))'
b["B22"].font = BOLD
b["B22"].fill = BEST
b["A23"] = "Payback of the overhaul against option B (years)"
b["B23"] = f'=IF(C17>D17-{CAPEX}/{LIFE},{CAPEX}/(C17-(D17-{CAPEX}/{LIFE})),"No payback")'
b["B23"].number_format = '0.0'

b["A26"] = "Sensitivity: annual cost (INR lakh) at different carrying rates"
b["A26"].font = BOLD
head(b, 27, ["Carrying rate", "A. Status quo", "B. Pre-build", "C. Overhaul + pre-build", "Cheapest"])
for i, rate in enumerate([0.10, 0.15, 0.20, 0.25, 0.30], start=28):
    b.cell(row=i, column=1, value=rate).number_format = '0%'
    b.cell(row=i, column=2, value="=$B$17/100000").number_format = LAKH
    b.cell(row=i, column=3, value=f"=($C$17-$C$12+$C$8*{STD}*A{i}*{HELD}/12)/100000").number_format = LAKH
    b.cell(row=i, column=4, value=f"=($D$17-$D$12+$D$8*{STD}*A{i}*{HELD}/12)/100000").number_format = LAKH
    b.cell(row=i, column=5, value=f'=INDEX({{"A","B","C"}},MATCH(MIN(B{i}:D{i}),B{i}:D{i},0))')

b["A35"] = "Limits: last winter's volumes are used as next winter's; the overhaul cost, its effect and the carrying rate are assumptions (yellow); "
b["A36"] = "moving production from Hosur to Haridwar changes which plant absorbs fixed cost but not the company's total, so it is left out."
b["A35"].font = b["A36"].font = NOTE
widths(b, [44, 24, 26, 30, 10])

# ------------------------------------------------------------------ Copper What-If
c = wb.create_sheet("Copper What-If", 3)
c["A1"] = "P1: wire gross margin % if copper and wire prices change (base: March 2026, after the October price rise)"
c["A1"].font = TITLE
c["A3"] = "Base month"
c["B3"] = "=Data_Wires!A13"
c["A4"] = "Net sales (INR)"
c["B4"] = "=Data_Wires!C13"
c["A5"] = "Cost at standard (INR)"
c["B5"] = "=Data_Wires!D13"
c["A6"] = "of which copper (INR)"
c["B6"] = "=Data_Wires!E13"
c["A7"] = "Gross margin % at base"
c["B7"] = "=(B4-B5)/B4"
c["A8"] = "Target gross margin %"
c["B8"] = 0.20
c["B8"].fill, c["B8"].font = YELLOW, BLUE
for r in range(4, 7):
    c[f"B{r}"].number_format = INR
c["B7"].number_format = c["B8"].number_format = PCT

c["A10"] = "Gross margin %: copper price change (rows) x wire price change (columns)"
c["A10"].font = BOLD
price_changes = [0, 0.03, 0.06, 0.09, 0.12, 0.15]
copper_changes = [-0.10, -0.05, 0, 0.05, 0.10, 0.15, 0.20, 0.30]
c.cell(row=11, column=1, value="Copper \\ price").font = BOLD
for j, p in enumerate(price_changes, start=2):
    cell = c.cell(row=11, column=j, value=p)
    cell.number_format, cell.font, cell.fill = '+0%;-0%;0%', BOLD, HEAD
for i, cu in enumerate(copper_changes, start=12):
    cell = c.cell(row=i, column=1, value=cu)
    cell.number_format, cell.font, cell.fill = '+0%;-0%;0%', BOLD, HEAD
    for j in range(2, 2 + len(price_changes)):
        col = get_column_letter(j)
        f = f"=($B$4*(1+{col}$11)-($B$5-$B$6+$B$6*(1+$A{i})))/($B$4*(1+{col}$11))"
        cell = c.cell(row=i, column=j, value=f)
        cell.number_format = PCT

c["A21"] = "Wire price rise needed to keep the target margin, by copper change"
c["A21"].font = BOLD
head(c, 22, ["Copper change", "Price rise needed", "Margin lost per month if price is not changed (INR)"])
for i, cu in enumerate(copper_changes, start=23):
    c.cell(row=i, column=1, value=cu).number_format = '+0%;-0%;0%'
    # price p such that (S(1+p) - C')/(S(1+p)) = target  ->  1+p = C' / (S (1 - target))
    cp = f"($B$5-$B$6+$B$6*(1+A{i}))"
    c.cell(row=i, column=2, value=f"=MAX(0,{cp}/($B$4*(1-$B$8))-1)").number_format = PCT
    c.cell(row=i, column=3, value=f"=$B$6*A{i}").number_format = INR
c["A32"] = "Copper is about 85% of wire cost, so a 10% copper rise needs about a 9% price rise to hold a 20% margin. Last year prices moved three months after copper did."
c["A32"].font = NOTE
widths(c, [30, 16, 18, 12, 12, 12, 12])

# ------------------------------------------------------------------ Read me
r = wb.create_sheet("Read me", 0)
lines = [
    ("Orvane Electricals (fictional): business case and copper what-if, FY 2025-26", TITLE),
    ("All data is synthetic, generated for this project.", NOTE),
    ("", None),
    ("Questions", BOLD),
    ("P2  How should the North be supplied with water heaters next winter? (WH Supply, Business Case)", None),
    ("P1  What does a copper price move do to wire margin, and what price rise holds it? (Copper What-If)", None),
    ("", None),
    ("How to use it", BOLD),
    ("Change the yellow cells on the Assumptions sheet (and the target margin on Copper What-If). Every result recalculates.", None),
    ("Blue cells come from the data; Data_* sheets are exported from PostgreSQL by src/export_reporting.py.", None),
    ("", None),
    ("Limits", BOLD),
    ("Next winter is assumed to look like last winter. The overhaul cost and its effect, the carrying rate and the warehouse", None),
    ("cost are assumptions to agree with the plant, supply chain and finance teams before a decision.", None),
]
for i, (t, f) in enumerate(lines, start=1):
    r.cell(row=i, column=1, value=t)
    if f:
        r.cell(row=i, column=1).font = f
widths(r, [120])

OUT.parent.mkdir(exist_ok=True)
wb.save(OUT)
print(f"Saved {OUT.relative_to(ROOT)}")
