"""
Monthly business review pack: one run builds reviews/review_pack_<month>.xlsx for the COO's office.

Before anything is written, billing is reconciled to the ledger for the month:
  - matched                          -> the pack is built
  - difference that reverses exactly in the next or previous month (a cut-off)
                                     -> the pack is built, with the difference stated on the summary page
  - any other difference             -> the pack is NOT built; the script stops with the amount to investigate

    python src/build_review_pack.py --month 2026-01 --port 5432
    (without --month: the latest month in the data)
"""
import argparse
import sys
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from db import add_connection_args, connect

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reviews"
BOLD, TITLE, NOTE = Font(bold=True), Font(bold=True, size=14), Font(italic=True, color="595959")
HEAD = PatternFill("solid", fgColor="DDE2E8")
RED, AMBER, GREEN = (PatternFill("solid", fgColor=c) for c in ("F8CBAD", "FFE699", "C6EFCE"))
TOLERANCE = 1.0      # INR


def q(cur, sql, params=()):
    cur.execute(sql, params)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def prev_month(m):
    y, mo = map(int, m.split("-"))
    return f"{y - 1}-12" if mo == 1 else f"{y}-{mo - 1:02d}"


def next_month(m):
    y, mo = map(int, m.split("-"))
    return f"{y + 1}-01" if mo == 12 else f"{y}-{mo + 1:02d}"


def reconcile(cur, month):
    """Returns (status, difference, note). Stops the run if a difference cannot be explained."""
    rec = {r["month"]: float(r["difference"]) for r in q(cur, "SELECT month, difference FROM rpt.reconciliation_summary")}
    diff = rec.get(month)
    if diff is None:
        sys.exit(f"STOP: no billing or ledger data for {month}")
    if abs(diff) <= TOLERANCE:
        return "Matched", diff, "Billing and ledger revenue agree."
    for other in (prev_month(month), next_month(month)):
        if other in rec and abs(rec[other] + diff) <= TOLERANCE:
            side = "booked in the ledger in" if diff < 0 else "booked in this month's ledger from"
            return ("Explained (cut-off)", diff,
                    f"Ledger differs from billing by INR {diff:,.0f}; the same amount reverses in {other}: "
                    f"invoices {side} {other}. Timing only; no revenue lost.")
    sys.exit(f"STOP: billing and ledger differ by INR {diff:,.0f} in {month} and it does not reverse in an adjacent "
             f"month. Investigate before the pack is published.")


def kpis(cur, month):
    sql = """
    SELECT month, SUM(net_sales) AS net_sales, SUM(gross_margin) AS gross_margin, SUM(contribution) AS contribution,
           SUM(units_invoiced) AS units, SUM(units_returned) AS units_returned, SUM(freight) AS freight
    FROM rpt.sales_monthly WHERE month IN (%s, %s) GROUP BY month"""
    rows = {r["month"]: r for r in q(cur, sql, (month, prev_month(month)))}
    extra = {r["month"]: r for r in q(cur, """
        SELECT m.month,
               (SELECT COALESCE(SUM(leakage), 0) FROM rpt.discount_leakage d WHERE d.month = m.month) AS leakage,
               (SELECT round(AVG(utilisation_pct), 1) FROM rpt.plant_cost p WHERE p.month = m.month) AS utilisation,
               (SELECT round(100.0 * SUM(shipped) / SUM(ordered), 2) FROM rpt.fill_rate f WHERE f.month = m.month) AS fill_rate,
               (SELECT COALESCE(SUM(extra_freight), 0) FROM rpt.extra_freight e WHERE e.month = m.month) AS extra_freight
        FROM (SELECT unnest(ARRAY[%s, %s]) AS month) m""", (month, prev_month(month)))}
    out = []
    for m in (month, prev_month(month)):
        r, e = rows.get(m), extra.get(m)
        if not r:
            out.append(None)
            continue
        ns = float(r["net_sales"])
        out.append({
            "Net sales (INR crore)": ns / 1e7,
            "Gross margin %": float(r["gross_margin"]) / ns,
            "Contribution margin %": float(r["contribution"]) / ns,
            "Units invoiced": float(r["units"]),
            "Units returned": float(r["units_returned"] or 0),
            "Discount above policy (INR lakh)": float(e["leakage"]) / 1e5,
            "Average line utilisation %": float(e["utilisation"]) / 100,
            "Fill rate %": float(e["fill_rate"]) / 100,
            "Extra freight off normal lanes (INR lakh)": float(e["extra_freight"]) / 1e5,
        })
    return out


def write_table(ws, row, title, rows, cols, fmts):
    ws.cell(row=row, column=1, value=title).font = BOLD
    for j, c in enumerate(cols, start=1):
        cell = ws.cell(row=row + 1, column=j, value=c)
        cell.font, cell.fill = BOLD, HEAD
        cell.alignment = Alignment(wrap_text=True)
    for i, r in enumerate(rows, start=row + 2):
        for j, c in enumerate(cols, start=1):
            v = r[c]
            cell = ws.cell(row=i, column=j, value=float(v) if hasattr(v, "is_finite") else v)
            if fmts.get(c):
                cell.number_format = fmts[c]
    return row + len(rows) + 3


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--month")
    add_connection_args(p)
    args = p.parse_args()
    con = connect(args)
    cur = con.cursor()
    month = args.month or q(cur, "SELECT MAX(month) AS m FROM rpt.sales_lines")[0]["m"]

    status, diff, note = reconcile(cur, month)          # stops here if the month does not reconcile
    now, before = kpis(cur, month)

    wb = Workbook()
    s = wb.active
    s.title = "Summary"
    s["A1"] = f"Orvane Electricals (fictional) — monthly business review, {month}"
    s["A1"].font = TITLE
    s["A2"] = "Synthetic data. Built by src/build_review_pack.py; every figure comes from the reporting views."
    s["A2"].font = NOTE
    s["A4"], s["B4"] = "Billing vs ledger", status
    s["B4"].fill = GREEN if status == "Matched" else AMBER
    s["A5"], s["B5"] = "Note", note
    s["B5"].alignment = Alignment(wrap_text=True)
    s.row_dimensions[5].height = 45
    for j, h in enumerate(["KPI", month, prev_month(month), "Change"], start=1):
        c = s.cell(row=7, column=j, value=h)
        c.font, c.fill = BOLD, HEAD
    for i, k in enumerate(now, start=8):
        s.cell(row=i, column=1, value=k)
        a, b = now[k], before[k] if before else None
        s.cell(row=i, column=2, value=a)
        s.cell(row=i, column=3, value=b)
        if b is not None:
            s.cell(row=i, column=4, value=f"=B{i}-C{i}")
        fmt = "0.0%" if "%" in k else ("#,##0.0" if "INR" in k else "#,##0")
        for col in (2, 3, 4):
            s.cell(row=i, column=col).number_format = fmt

    # What moved gross margin this month: largest bridge effects across categories
    bridge = q(cur, """SELECT category, volume, mix, price, cost, returns, change FROM rpt.margin_bridge
                       WHERE scope = 'All' AND month = %s ORDER BY category""", (month,))
    effects = []
    for r in bridge:
        for e in ("volume", "mix", "price", "cost", "returns"):
            effects.append((abs(float(r[e])), r["category"], e, float(r[e])))
    effects.sort(reverse=True)
    s["A19"] = "What moved gross margin against last month (largest effects)"
    s["A19"].font = BOLD
    for i, (_, cat, e, v) in enumerate(effects[:4], start=20):
        s.cell(row=i, column=1, value=f"{cat}: {e} effect")
        s.cell(row=i, column=2, value=v / 1e5).number_format = '+#,##0.0;-#,##0.0'
        s.cell(row=i, column=3, value="INR lakh")
    s.column_dimensions["A"].width, s.column_dimensions["B"].width = 44, 60
    for col in "CD":
        s.column_dimensions[col].width = 16

    lakh = '#,##0.0;-#,##0.0'
    b = wb.create_sheet("Margin bridge")
    rows = [{k: (float(v) / 1e5 if k not in ("category",) else v) for k, v in r.items()} for r in bridge]
    write_table(b, 1, f"Gross margin change by category, {month} vs {prev_month(month)} (INR lakh)", rows,
                ["category", "volume", "mix", "price", "cost", "returns", "change"],
                {c: lakh for c in ["volume", "mix", "price", "cost", "returns", "change"]})
    b.column_dimensions["A"].width = 16

    pl = wb.create_sheet("Plants")
    rows = q(cur, """SELECT line, plant, units, downtime_days, utilisation_pct, actual_cost_per_unit, std_cost_per_unit,
                            round(conversion_variance / 1e5, 1) AS conversion_variance_lakh
                     FROM rpt.plant_cost WHERE month = %s ORDER BY line""", (month,))
    nxt = write_table(pl, 1, f"Production lines, {month}", rows, list(rows[0].keys()), {"units": "#,##0"})
    for i, r in enumerate(rows, start=3):
        if r["downtime_days"] and r["downtime_days"] > 0:
            for j in range(1, 9):
                pl.cell(row=i, column=j).fill = RED

    sp = wb.create_sheet("Supply")
    rows = q(cur, """SELECT region, category, fill_rate_pct FROM rpt.fill_rate WHERE month = %s AND fill_rate_pct < 100
                     ORDER BY fill_rate_pct""", (month,))
    nxt = write_table(sp, 1, "Fill rate below 100%", rows or [{"region": "None", "category": "", "fill_rate_pct": ""}],
                      ["region", "category", "fill_rate_pct"], {})
    rows = q(cur, """SELECT from_plant, to_warehouse, category, units, round(extra_freight / 1e5, 1) AS extra_freight_lakh
                     FROM rpt.extra_freight WHERE month = %s""", (month,))
    write_table(sp, nxt, "Extra freight off normal lanes",
                rows or [{"from_plant": "None", "to_warehouse": "", "category": "", "units": "", "extra_freight_lakh": ""}],
                ["from_plant", "to_warehouse", "category", "units", "extra_freight_lakh"], {})

    rk = wb.create_sheet("Risks and opportunities")
    rows = q(cur, """SELECT id, type, item, round(value_inr / 1e5, 1) AS value_lakh, basis, owner, action
                     FROM rpt.risk_opportunity ORDER BY type DESC, id""")
    write_table(rk, 1, "Register (values recalculated from the data at each run)", rows, list(rows[0].keys()),
                {"value_lakh": lakh})
    for col, w in zip("ABCDEFG", [6, 12, 40, 12, 50, 26, 50]):
        rk.column_dimensions[col].width = w

    for ws in (b, pl, sp):
        for j in range(1, 9):
            ws.column_dimensions[get_column_letter(j)].width = max(ws.column_dimensions[get_column_letter(j)].width or 0, 14)

    OUT.mkdir(exist_ok=True)
    path = OUT / f"review_pack_{month}.xlsx"
    wb.save(path)
    con.close()
    print(f"{month}: billing vs ledger {status} (difference INR {diff:,.0f})")
    print(f"Saved {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
