"""Prints the analysis views as tables.

    python src/show.py sales --port 5432
Topics: sales, margin, bridge, plants, supply, recon, register, notes
"""
import argparse

import pandas as pd

from db import add_connection_args, connect

pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 30)
pd.set_option("display.max_rows", 200)

TOPICS = {
    "sales": [
        ("Net sales by month and category (INR crore)",
         """SELECT month, category, round(SUM(net_sales) / 1e7, 1) AS v FROM rpt.sales_monthly GROUP BY 1, 2""",
         ("month", "category", "v")),
        ("Net sales by region (INR crore, full year)",
         """SELECT region, round(SUM(net_sales) / 1e7, 1) AS net_sales_cr,
                   round(100 * SUM(net_sales) / SUM(SUM(net_sales)) OVER (), 1) AS share_pct
            FROM rpt.sales_monthly GROUP BY 1 ORDER BY 2 DESC""", None),
        ("Units invoiced by month and channel",
         """SELECT month, channel, units AS v FROM rpt.channel_trend""", ("month", "channel", "v")),
    ],
    "margin": [
        ("Gross margin % by month and category",
         """SELECT month, category, gross_margin_pct AS v FROM rpt.margin_by_category""", ("month", "category", "v")),
        ("Gross vs contribution margin by channel (full year)",
         """SELECT channel, units, round(net_sales / 1e7, 1) AS net_sales_cr, gross_margin_pct, freight_pct, contribution_pct
            FROM rpt.margin_by_channel ORDER BY contribution_pct DESC""", None),
        ("Fans: economy share of units by region and month",
         """SELECT month, region, unit_share AS v FROM rpt.segment_mix WHERE category = 'Fans' AND segment = 'Economy'""",
         ("month", "region", "v")),
    ],
    "bridge": [
        ("Margin bridge, all regions: change in gross margin vs previous month (INR lakh)",
         """SELECT month, category, round(volume / 1e5, 1) AS volume, round(mix / 1e5, 1) AS mix,
                   round(price / 1e5, 1) AS price, round(cost / 1e5, 1) AS cost, round(returns / 1e5, 1) AS returns,
                   round(change / 1e5, 1) AS change
            FROM rpt.margin_bridge WHERE scope = 'All' AND category IN ('Wires', 'Water heaters')
            ORDER BY category, month""", None),
        ("Fans in the South: mix effect by month (INR lakh)",
         """SELECT month, round(volume / 1e5, 1) AS volume, round(mix / 1e5, 1) AS mix, round(change / 1e5, 1) AS change
            FROM rpt.margin_bridge WHERE scope = 'South' AND category = 'Fans' ORDER BY month""", None),
        ("Price effect by region, all categories (INR lakh)",
         """SELECT month, scope AS region, round(SUM(price) / 1e5, 1) AS v FROM rpt.margin_bridge
            WHERE scope <> 'All' GROUP BY 1, 2""", ("month", "region", "v")),
        ("Discount above policy (INR lakh), distributors by region",
         """SELECT month, region, round(leakage / 1e5, 1) AS v FROM rpt.discount_leakage WHERE channel = 'Distributor'""",
         ("month", "region", "v")),
        ("Check: volume + mix + price + cost + returns = change (rows that do not add up)",
         """SELECT COUNT(*) AS rows_checked,
                   COUNT(*) FILTER (WHERE abs(volume + mix + price + cost + returns - change) > 5) AS rows_off
            FROM rpt.margin_bridge""", None),
    ],
    "plants": [
        ("Utilisation % by line and month",
         """SELECT month, line, utilisation_pct AS v FROM rpt.plant_cost""", ("month", "line", "v")),
        ("Conversion cost per unit (INR) by line and month",
         """SELECT month, line, conversion_per_unit AS v FROM rpt.plant_cost""", ("month", "line", "v")),
        ("Baddi STB-L1: actual vs standard",
         """SELECT month, units, downtime_days, utilisation_pct, actual_cost_per_unit, std_cost_per_unit,
                   round(conversion_variance / 1e5, 1) AS conversion_variance_lakh
            FROM rpt.plant_cost WHERE line = 'STB-L1' ORDER BY month""", None),
        ("Cost variance by plant, full year (INR lakh; above zero = cost more than standard)",
         """SELECT plant, round(SUM(material_variance) / 1e5, 1) AS material_variance,
                   round(SUM(conversion_variance) / 1e5, 1) AS conversion_variance
            FROM rpt.plant_cost GROUP BY plant ORDER BY plant""", None),
        ("Return rate by invoice month: WH006 by plant vs all other products",
         """SELECT invoice_month, CASE WHEN material = 'WH006' THEN 'WH006 ' || plant ELSE 'All other products' END AS grp,
                   round(SUM(units_returned)::NUMERIC / SUM(units_invoiced), 4) AS v
            FROM rpt.return_rates GROUP BY 1, 2""", ("invoice_month", "grp", "v")),
    ],
    "supply": [
        ("Water heaters to the North warehouse: freight per unit by lane",
         """SELECT month, from_plant || ' to ' || to_warehouse AS lane, units, freight_per_unit FROM rpt.lane_freight
            WHERE category = 'Water heaters' AND to_warehouse = 'WN' ORDER BY month, lane""", None),
        ("Extra freight from supplying a warehouse off its normal lane (INR lakh)",
         """SELECT month, from_plant || ' to ' || to_warehouse AS lane, category, units,
                   round(extra_freight / 1e5, 1) AS extra_freight_lakh
            FROM rpt.extra_freight ORDER BY month""", None),
        ("Short shipments: units ordered but not shipped (sales and margin lost, INR lakh)",
         """SELECT month, region, category, units_short, round(sales_lost / 1e5, 1) AS sales_lost_lakh,
                   round(margin_lost / 1e5, 1) AS margin_lost_lakh
            FROM rpt.short_shipments ORDER BY month""", None),
        ("Fill rate % (shipped / ordered), water heaters by region",
         """SELECT month, region, fill_rate_pct AS v FROM rpt.fill_rate WHERE category = 'Water heaters'""",
         ("month", "region", "v")),
        ("Days of stock at month end, water heaters by region",
         """SELECT month, region, days_of_stock AS v FROM rpt.days_of_stock WHERE category = 'Water heaters'""",
         ("month", "region", "v")),
    ],
    "recon": [
        ("Billing register vs ledger revenue by month (INR crore)",
         """SELECT month, round(billing_net_sales / 1e7, 2) AS billing_cr, round(ledger_revenue / 1e7, 2) AS ledger_cr,
                   round(difference / 1e7, 2) AS difference_cr, status
            FROM rpt.reconciliation_summary ORDER BY month""", None),
        ("Invoices dated in the last 4 days of November and December (INR crore)",
         """SELECT billing_date, invoices, round(net_value / 1e7, 2) AS net_value_cr
            FROM rpt.month_end_invoices WHERE month IN ('2025-11', '2025-12') ORDER BY billing_date""", None),
    ],
    "register": [
        ("Risk and opportunity register (INR lakh)",
         """SELECT id, type, item, round(value_inr / 1e5, 1) AS value_lakh, owner FROM rpt.risk_opportunity ORDER BY type DESC, id""",
         None),
    ],
    "notes": [
        ("Field notes by theme and region (full year, themes tagged by the language model)",
         """SELECT theme, region, SUM(notes) AS v FROM rpt.field_note_themes GROUP BY 1, 2""", ("theme", "region", "v")),
        ("West: share of field notes about competitor pricing vs premium share of fan units",
         """SELECT month, competitor_note_share, premium_fan_share FROM rpt.west_competitor_signal ORDER BY month""", None),
    ],
}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("topic", choices=TOPICS)
    add_connection_args(p)
    args = p.parse_args()
    con = connect(args)
    for title, sql, pivot in TOPICS[args.topic]:
        with con.cursor() as cur:
            cur.execute(sql)
            df = pd.DataFrame(cur.fetchall(), columns=[d[0] for d in cur.description])
        if pivot:
            df = df.pivot(index=pivot[0], columns=pivot[1], values=pivot[2])
            df.columns.name = None
        print(f"\n== {title}\n{df.to_string()}")
    con.close()


if __name__ == "__main__":
    main()
