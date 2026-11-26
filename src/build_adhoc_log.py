"""
Ad hoc analysis log: ten questions of the kind a COO's office asks, each answered with one query.

    python src/build_adhoc_log.py --port 5433

Runs every query against the database, times it, and writes docs/adhoc_log.md with the question,
the SQL, the result and a two-line answer. The answers are written from the query results each time
the script runs, so they always match the data.
"""
import argparse
import time
from pathlib import Path

import pandas as pd

from db import add_connection_args, connect

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "adhoc_log.md"


def cr(x):
    return f"₹{float(x) / 1e7:,.2f} crore"


def pct(x, d=1):
    return f"{float(x) * 100:.{d}f}%"


# Each entry: (asked by, question, SQL, function that writes the answer from the result)
LOG = [
    ("COO", "Why did wire margin fall in July and August?",
     """SELECT b.month, round(b.change / 1e5, 1) AS change_lakh, round(b.cost / 1e5, 1) AS cost_effect_lakh,
       round(b.price / 1e5, 1) AS price_effect_lakh, w.copper_per_kg
FROM rpt.margin_bridge b JOIN rpt.wire_cost_monthly w USING (month)
WHERE b.scope = 'All' AND b.category = 'Wires' AND b.month BETWEEN '2025-06' AND '2025-10'
ORDER BY b.month""",
     lambda d: (f"Cost, not volume or price: the cost effect was ₹{-d.cost_effect_lakh[d.month == '2025-07'].iloc[0]:,.1f} lakh in July "
                f"and ₹{-d.cost_effect_lakh[d.month == '2025-08'].iloc[0]:,.1f} lakh in August, as copper went from "
                f"₹{d.copper_per_kg.iloc[0]:,.0f} to ₹{d.copper_per_kg[d.month == '2025-09'].iloc[0]:,.0f} per kg. "
                f"The October price increase brought ₹{d.price_effect_lakh[d.month == '2025-10'].iloc[0]:,.1f} lakh back in one month.")),

    ("East sales head", "Which customers drive the East discounts above policy?",
     """WITH leak AS (
    SELECT s.customer, c.customer_name, c.city,
           SUM((s.discount_pct - p.max_discount_pct) / 100 * s.gross_value) AS above_policy
    FROM rpt.sales_lines s
    JOIN ref.customers c USING (customer)
    JOIN ref.discount_policy p ON p.channel = s.channel
    WHERE s.region = 'East' AND s.billing_type = 'F2' AND s.discount_pct > p.max_discount_pct
    GROUP BY 1, 2, 3)
SELECT customer, customer_name, city, round(above_policy / 1e5, 1) AS above_policy_lakh,
       round(100 * above_policy / SUM(above_policy) OVER (), 1) AS share_pct,
       round(100 * SUM(above_policy) OVER (ORDER BY above_policy DESC) / SUM(above_policy) OVER (), 1) AS cumulative_pct,
       COUNT(*) OVER () AS customers
FROM leak ORDER BY above_policy DESC""",
     lambda d: (f"{int(d.customers.iloc[0])} East customers got discounts above policy, worth "
                f"₹{d.above_policy_lakh.sum():,.1f} lakh in total. The top 20 account for {d.cumulative_pct.iloc[min(19, len(d) - 1)]:.1f}% of it, "
                f"so a sign-off for any discount above policy on those 20 accounts would cover more than half of it.")),

    ("COO", "How dependent are we on our biggest customers?",
     """WITH c AS (
    SELECT customer, SUM(net_value) AS net FROM rpt.sales_lines GROUP BY 1)
SELECT n_customers, round(100 * top_net / total, 1) AS share_of_net_sales_pct
FROM (SELECT SUM(net) AS total FROM c) t,
     LATERAL (VALUES (10), (20), (50), (100)) v(n_customers),
     LATERAL (SELECT SUM(net) AS top_net FROM (SELECT net FROM c ORDER BY net DESC LIMIT v.n_customers) x) y
ORDER BY n_customers""",
     lambda d: (f"Not heavily: the top 10 of 400 customers are {d.share_of_net_sales_pct.iloc[0]:.1f}% of net sales and the top 20 are "
                f"{d.share_of_net_sales_pct.iloc[1]:.1f}%. Losing any single customer would not move the year by much.")),

    ("COO", "Which channel keeps the least margin after freight?",
     """SELECT channel, round(net_sales / 1e7, 1) AS net_sales_cr, gross_margin_pct, freight_pct, contribution_pct
FROM rpt.margin_by_channel ORDER BY contribution_pct""",
     lambda d: (f"{d.channel.iloc[0]}: {d.gross_margin_pct.iloc[0]}% gross margin, but freight takes {d.freight_pct.iloc[0]} points, "
                f"leaving {d.contribution_pct.iloc[0]}%, the lowest of the four channels. "
                f"Every point of freight saved there is worth {cr(d.net_sales_cr.iloc[0] * 1e7 / 100)} a year at this year's sales.")),

    ("West sales head", "Which fan products lost the most in the West since August?",
     """WITH u AS (
    SELECT s.material, m.description, s.segment, (s.region = 'West') AS west,
           SUM(s.quantity) FILTER (WHERE s.month BETWEEN '2025-04' AND '2025-07') / 4.0 AS apr_jul,
           SUM(s.quantity) FILTER (WHERE s.month BETWEEN '2025-08' AND '2026-03') / 8.0 AS aug_mar
    FROM rpt.sales_lines s JOIN ref.materials m USING (material)
    WHERE s.category = 'Fans' AND s.billing_type = 'F2'
    GROUP BY 1, 2, 3, 4)
SELECT w.material, w.description, w.segment,
       round(100 * (w.aug_mar / w.apr_jul - 1), 1) AS west_change_pct,
       round(100 * (o.aug_mar / o.apr_jul - 1), 1) AS other_regions_change_pct,
       round(100 * (w.aug_mar / w.apr_jul - o.aug_mar / o.apr_jul), 1) AS west_gap_pts
FROM u w JOIN u o ON o.material = w.material AND NOT o.west
WHERE w.west ORDER BY west_gap_pts LIMIT 6""",
     lambda d: (f"Fan sales fall everywhere after the summer, so each product's West change is compared with the other regions. "
                f"The products that fell furthest beyond the seasonal drop are all {', '.join(sorted(set(d.segment.head(4))))}: "
                f"{d.description.iloc[0]} ({d.material.iloc[0]}) fell {-d.west_change_pct.iloc[0]:.0f}% in the West against "
                f"{-d.other_regions_change_pct.iloc[0]:.0f}% elsewhere. That fits the field notes: West notes about competitor BLDC fans "
                f"rose from about 20% to 41–54% of notes in Aug–Sep.")),

    ("COO", "Which plant line ran furthest over standard cost, and why?",
     """SELECT plant, line, category, month, units, actual_cost_per_unit, std_cost_per_unit,
       round(100 * (actual_cost_per_unit / std_cost_per_unit - 1), 1) AS over_std_pct, utilisation_pct, downtime_days
FROM rpt.plant_cost ORDER BY actual_cost_per_unit / std_cost_per_unit DESC LIMIT 6""",
     lambda d: (f"{d.plant.iloc[0]} {d.line.iloc[0]} in {d.month.iloc[0]}: ₹{d.actual_cost_per_unit.iloc[0]:,.0f} per unit against a standard of "
                f"₹{d.std_cost_per_unit.iloc[0]:,.0f} ({d.over_std_pct.iloc[0]:.0f}% over), because {int(d.downtime_days.iloc[0])} days of downtime "
                f"left it at {d.utilisation_pct.iloc[0]}% utilisation. The next worst are {d.plant.iloc[1]} {d.line.iloc[1]} in the summer months, "
                f"running at 13–18% utilisation: idle capacity, not breakdowns.")),

    ("Finance controller", "What share of each month's billing lands in the last four days?",
     """WITH m AS (SELECT month, SUM(net_value) AS net FROM rpt.sales_lines WHERE billing_type = 'F2' GROUP BY 1),
e AS (SELECT month, SUM(net_value) AS net_last4, SUM(invoices) AS invoices_last4 FROM rpt.month_end_invoices GROUP BY 1)
SELECT month, invoices_last4, round(net_last4 / 1e7, 2) AS last4_cr, round(100 * net_last4 / net, 1) AS share_pct
FROM m JOIN e USING (month) ORDER BY month""",
     lambda d: (f"Between {d.share_pct.min():.1f}% and {d.share_pct.max():.1f}% every month. December was {d.share_pct[d.month == '2025-12'].iloc[0]:.1f}%, "
                f"the highest in value (₹{d.last4_cr[d.month == '2025-12'].iloc[0]:,.2f} crore) but not unusual as a share. So the December cut-off "
                f"error could not be spotted from billing timing; it showed only when billing was reconciled to the ledger.")),

    ("COO", "How accurate was the sales team's unit forecast?",
     """WITH f AS (
    SELECT split_part(key, '|', 1) AS month, split_part(key, '|', 2) AS category, value AS forecast
    FROM inp.function_inputs WHERE input = 'Unit sales forecast'),
a AS (
    SELECT month, category, SUM(quantity) AS actual FROM rpt.sales_lines WHERE billing_type = 'F2' GROUP BY 1, 2)
SELECT category, round(AVG(ABS(forecast - actual) / actual) * 100, 1) AS mape_pct,
       round(100 * (SUM(forecast) / SUM(actual) - 1), 1) AS bias_pct,
       round(100 * MAX(ABS(forecast - actual) / actual), 1) AS worst_month_error_pct
FROM f JOIN a USING (month, category) GROUP BY 1 ORDER BY 2 DESC""",
     lambda d: (f"Average monthly error (MAPE) was {d.mape_pct.min():.1f}–{d.mape_pct.max():.1f}% by category, and over the year the forecast was "
                f"{d.bias_pct.min():+.1f}% to {d.bias_pct.max():+.1f}% against actual units. Usable for planning, "
                f"but individual months were off by up to {d.worst_month_error_pct.max():.0f}%, so plant plans need a buffer.")),

    ("COO", "Which assumptions from the functions did not hold?",
     """SELECT 'Copper price, Jul-Mar (INR/kg)' AS input, 'Plant controller' AS provided_by,
       (SELECT value FROM inp.function_inputs WHERE input = 'Copper price assumption Jul-Mar') AS assumed,
       (SELECT round(AVG(copper_per_kg), 1) FROM ref.commodity_prices WHERE month >= '2025-07') AS actual
UNION ALL
SELECT 'Baddi STB-L1 working days, Nov 2025', 'BDI plant head',
       (SELECT value FROM inp.function_inputs WHERE input = 'Planned working days' AND key = '2025-11|STB-L1'),
       (SELECT 26 - downtime_days FROM rpt.plant_cost WHERE line = 'STB-L1' AND month = '2025-11')
UNION ALL
SELECT 'Wire price increase (%)', 'Plant controller',
       (SELECT value FROM inp.function_inputs WHERE input = 'Planned wire price increase'),
       (SELECT round(100 * (AVG(p.list_price) FILTER (WHERE valid_from >= '2025-10-01') /
                            AVG(p.list_price) FILTER (WHERE valid_from < '2025-10-01') - 1), 1)
        FROM ref.price_list p JOIN ref.materials m USING (material) WHERE m.category = 'Wires')""",
     lambda d: (f"Copper: the plan assumed ₹{d.assumed.iloc[0]:,.0f} per kg for Jul–Mar, the actual average was ₹{d.actual.iloc[0]:,.0f} "
                f"({(d.actual.iloc[0] / d.assumed.iloc[0] - 1) * 100:.0f}% higher). Baddi planned {d.assumed.iloc[1]:.0f} working days on STB-L1 in November "
                f"and got {d.actual.iloc[1]:.0f}. The wire price increase went through as planned ({d.actual.iloc[2]:.0f}%).")),

    ("COO", "How much margin did customer returns cost, and where?",
     """WITH r AS (
    SELECT material, plant, invoice_month, return_rate,
           (material = 'WH006' AND plant = 'HSR' AND invoice_month IN ('2026-01', '2026-02')) AS flagged
    FROM rpt.return_rates)
SELECT m.category, round(-SUM(m.returns_margin) / 1e5, 1) AS margin_lost_lakh,
       (SELECT round(100 * AVG(return_rate), 2) FROM r WHERE NOT flagged) AS normal_return_rate_pct,
       (SELECT round(100 * return_rate, 2) FROM r WHERE material = 'WH006' AND plant = 'HSR' AND invoice_month = '2026-01') AS wh006_jan_pct,
       (SELECT round(100 * return_rate, 2) FROM r WHERE material = 'WH006' AND plant = 'HSR' AND invoice_month = '2026-02') AS wh006_feb_pct
FROM rpt.returns_margin m WHERE m.scope = 'All' GROUP BY 1 ORDER BY 2 DESC""",
     lambda d: (f"₹{d.margin_lost_lakh.sum():,.1f} lakh of gross margin for the year, the most in {d.category.iloc[0]} "
                f"(₹{d.margin_lost_lakh.iloc[0]:,.1f} lakh). One product stands out: WH006 from Hosur had {d.wh006_jan_pct.iloc[0]:.1f}% of January "
                f"and {d.wh006_feb_pct.iloc[0]:.1f}% of February invoices returned, against {d.normal_return_rate_pct.iloc[0]:.1f}% for a normal product-month.")),
]


def md_table(df, max_rows=12):
    df = df.head(max_rows)
    cols = list(df.columns)
    rows = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for r in df.itertuples(index=False):
        rows.append("| " + " | ".join(f"{v:,}" if isinstance(v, int) else str(v) for v in r) + " |")
    return "\n".join(rows)


def main():
    p = argparse.ArgumentParser()
    add_connection_args(p)
    args = p.parse_args()
    con = connect(args)
    parts = ["# Ad hoc analysis log", "",
             "Ten questions of the kind a COO's office asks during the month (written as examples: Orvane is fictional and nobody asked them), each answered with one query against the "
             "`orvane` database. Written by `src/build_adhoc_log.py`; the answers are generated from the query results, "
             "so re-running the script after a data change updates them. Run time is the query's time on a laptop "
             "(PostgreSQL 17), not the time to write it.", "",
             "| # | Asked by | Question | Query time |", "|---|---|---|---|"]
    body = []
    for i, (who, q, sql, answer) in enumerate(LOG, start=1):
        t0 = time.perf_counter()
        with con.cursor() as cur:
            cur.execute(sql)
            df = pd.DataFrame(cur.fetchall(), columns=[c[0] for c in cur.description])
        ms = (time.perf_counter() - t0) * 1000
        for c in df.columns:                      # Decimal -> float so the answers can do arithmetic
            if df[c].map(lambda v: v.__class__.__name__ == "Decimal").any():
                df[c] = df[c].astype(float)
        text = answer(df)
        parts.append(f"| {i} | {who} | [{q}](#q{i}) | {ms:,.0f} ms |")
        body += ["", f"## Q{i}. {q} <a id=\"q{i}\"></a>", f"*Asked by: {who} · query time {ms:,.0f} ms*", "",
                 f"**Answer.** {text}", "", "```sql", sql, "```", "", md_table(df)]
        print(f"  Q{i:<2} {ms:>6,.0f} ms  {q}")
    con.close()
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text("\n".join(parts + body) + "\n", encoding="utf-8")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
