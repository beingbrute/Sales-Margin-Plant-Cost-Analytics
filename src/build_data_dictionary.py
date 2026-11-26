"""
Data dictionary: every table and view in the orvane database, with its columns and types.

    python src/build_data_dictionary.py --port 5433

Column names and types are read from the database, so the dictionary always matches what is loaded.
Descriptions of each object and of the columns that need one are kept below. The script warns about
any table or view that has no description, so a new view cannot be added without documenting it.
"""
import argparse
from pathlib import Path

from db import add_connection_args, connect

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "data_dictionary.md"

SCHEMAS = {
    "ref": "Master data (SAP: plants, materials, condition records, customers)",
    "sd": "Sales and distribution: billing documents",
    "pp": "Production planning: production orders and line capacity",
    "mm": "Materials management: stock transfers and warehouse stock",
    "fi": "Finance: general ledger revenue",
    "inp": "Inputs from functions and the sales team",
    "etl": "Data preparation records",
    "rpt": "Reporting views: every metric is defined here once and read by Excel, Power BI and the scripts",
}

OBJECTS = {
    "ref.plants": "One row per plant (SAP T001W).",
    "ref.lines": "One row per production line, with the category it makes and its fixed cost per month.",
    "ref.warehouses": "One row per regional warehouse; region links customers to warehouses.",
    "ref.materials": "One row per product (MARA/MARC): category, segment, list price, producing plant and line.",
    "ref.bill_of_materials": "Copper, steel and plastic per unit of each product, used to cost raw material.",
    "ref.standard_costs": "Standard cost per unit by product and month (CK11 cost estimate); raw material follows commodity prices.",
    "ref.price_list": "List price per product with the date it applies from (PR00). Wires have a new price from 1 October 2025.",
    "ref.discount_policy": "Maximum discount allowed per channel (K007).",
    "ref.customers": "One row per customer (KNA1/KNVV): channel, region, city.",
    "ref.commodity_prices": "Copper, steel and plastic price per kg by month.",
    "sd.billing": "One row per billing line (VBRK/VBRP), after cleaning. F2 = invoice, G2 = credit note (negative quantity and value).",
    "pp.production_orders": "One row per production order (AFKO/AFPO): planned and actual quantity, actual cost, machine hours.",
    "pp.plant_capacity": "One row per line and month: available machine hours, downtime days, fixed cost.",
    "mm.stock_transfers": "One row per plant-to-warehouse shipment (STO), with freight cost.",
    "mm.warehouse_stock": "Closing stock per warehouse, product and month end (MB52).",
    "fi.gl_revenue": "Revenue booked in the ledger per month and category (FAGLFLEXT); used to reconcile billing.",
    "inp.function_inputs": "Inputs register: what each function provided (sales forecast, planned working days, freight rates, cost assumptions). Template: templates/function_inputs_template.xlsx.",
    "inp.field_notes": "Sales team visit notes, one per visit.",
    "inp.field_note_themes": "Theme of each field note, tagged by a local language model (src/tag_field_notes.py).",
    "etl.cleaning_log": "One row per cleaning rule: rows changed or removed and the net value removed.",
    "rpt.sales_lines": "Materialized view. One row per billing line with product, customer, margin and freight; the base of every sales metric. Refresh after loading.",
    "rpt.sales_monthly": "Units, gross sales, discount, net sales, COGS, gross margin, freight and contribution by month, category, region and channel.",
    "rpt.margin_by_category": "Gross and contribution margin % by month and category (ratio of totals).",
    "rpt.margin_by_channel": "Full-year gross margin %, freight % and contribution % by channel.",
    "rpt.channel_trend": "Units and net sales by month and channel.",
    "rpt.segment_mix": "Share of each segment (economy, mid, premium) in a category's units, by month and region.",
    "rpt.bridge_base": "Units, net sales and standard cost by month, scope (All or a region), category and product; input to the margin bridge.",
    "rpt.returns_margin": "Gross margin lost to credit notes by month, scope and category.",
    "rpt.margin_bridge": "Month-on-month change in gross margin split into volume, mix, price, cost and returns; the five add up exactly to change.",
    "rpt.margin_bridge_long": "The margin bridge with one row per effect, for the Power BI waterfall.",
    "rpt.discount_leakage": "Discount given above the channel policy, by month, region and channel.",
    "rpt.plant_cost": "Actual vs standard cost, cost per unit and utilisation by line and month.",
    "rpt.return_rates": "Units returned ÷ units invoiced by product, plant and the month the goods were invoiced.",
    "rpt.lane_freight": "Freight per unit by month, plant-to-warehouse lane and category.",
    "rpt.fill_rate": "Invoiced quantity ÷ ordered quantity by month, region and category.",
    "rpt.days_of_stock": "Closing stock ÷ average daily sales by month, region and category.",
    "rpt.extra_freight": "Freight paid above the normal lane when a warehouse is supplied from another plant.",
    "rpt.short_shipments": "Units ordered but not shipped, with the sales and margin lost.",
    "rpt.revenue_reconciliation": "Billing net sales vs ledger revenue by month and category.",
    "rpt.reconciliation_summary": "Billing vs ledger by month with status (Matched or Difference).",
    "rpt.month_end_invoices": "Invoices and value billed in the last four days of each month (cut-off check).",
    "rpt.risk_opportunity": "Risk and opportunity register; every value is calculated from the views above.",
    "rpt.wh_supply_monthly": "North water heater supply by month: ordered, shipped from each plant, short, Haridwar capacity; feeds the business case.",
    "rpt.wire_cost_monthly": "Wire units, net sales, standard cost, copper cost and copper price by month; feeds the copper what-if.",
    "rpt.field_note_themes": "Field notes per theme by month and region, with each theme's share of the region's notes.",
    "rpt.west_competitor_signal": "West: share of field notes about competitor pricing vs premium share of fan units, by month.",
}

COLUMNS = {
    "material": "Product code (ref.materials)",
    "customer": "Customer code (ref.customers)",
    "plant": "HDW Haridwar, BDI Baddi, HSR Hosur",
    "from_plant": "HDW Haridwar, BDI Baddi, HSR Hosur",
    "line": "Production line (ref.lines)",
    "warehouse": "WN Gurugram, WS Bengaluru, WE Kolkata, WW Bhiwandi",
    "to_warehouse": "WN Gurugram, WS Bengaluru, WE Kolkata, WW Bhiwandi",
    "region": "North, South, East or West",
    "channel": "Distributor, Modern retail, E-commerce or Institutional",
    "category": "Fans, Wires, Water heaters or Stabilisers",
    "valid_from": "Date the price or cost applies from",
    "month": "Calendar month, text YYYY-MM",
    "scope": "All = whole company; otherwise a region",
    "segment": "Economy, Mid or Premium",
    "billing_type": "F2 = invoice, G2 = credit note",
    "reference_doc": "For a credit note: the invoice it reverses",
    "invoice_month": "Month of the original invoice (for credit notes, not the month the credit note was raised)",
    "ordered_qty": "Quantity the customer ordered; quantity is what was invoiced",
    "discount_pct": "Discount given on the line, % of list price",
    "cost_at_standard": "Quantity × standard cost for the billing month",
    "gross_margin": "Net sales − cost at standard",
    "contribution": "Gross margin − freight",
    "net_value": "Value after discount; negative on credit notes",
    "utilisation_pct": "Machine hours used ÷ machine hours available × 100",
    "unit_share": "Share of the category's units (0–1)",
    "share": "Share of the region's notes that month (0–1)",
    "return_rate": "Units returned ÷ units invoiced (0–1)",
    "leakage": "Gross value × (discount % − policy maximum), where above policy",
    "fill_rate_pct": "Invoiced ÷ ordered × 100",
    "key": "Month|category, month|line or plant|warehouse, depending on the input",
    "value_inr": "Value in INR for the year unless the basis says otherwise",
    "status": "Matched or Difference",
    "effect_order": "Sort order of the effect in the waterfall",
}


def main():
    p = argparse.ArgumentParser()
    add_connection_args(p)
    args = p.parse_args()
    con = connect(args)
    with con.cursor() as cur:
        cur.execute("""
            SELECT n.nspname, c.relname,
                   CASE c.relkind WHEN 'r' THEN 'table' WHEN 'v' THEN 'view' WHEN 'm' THEN 'materialized view' END,
                   a.attname, format_type(a.atttypid, a.atttypmod), a.attnum
            FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
            JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum > 0 AND NOT a.attisdropped
            WHERE n.nspname = ANY(%s) AND c.relkind IN ('r', 'v', 'm')
            ORDER BY n.nspname, c.relname, a.attnum""", (list(SCHEMAS),))
        rows = cur.fetchall()
        counts = {}
        for schema, name, kind in {(r[0], r[1], r[2]) for r in rows}:
            if kind != "view":                   # count rows in tables and the materialized view
                cur.execute(f"SELECT COUNT(*) FROM {schema}.{name}")
                counts[f"{schema}.{name}"] = cur.fetchone()[0]
    con.close()

    objects = {}
    for schema, name, kind, col, typ, _ in rows:
        objects.setdefault((schema, name, kind), []).append((col, typ))

    missing = [f"{s}.{n}" for (s, n, _) in objects if f"{s}.{n}" not in OBJECTS]
    out = ["# Data dictionary", "",
           "Every table and view in the `orvane` database. Written by `src/build_data_dictionary.py` from the database "
           "itself, so names and types match what is loaded. Metric definitions: `docs/design.md`, section 3. "
           "All data is synthetic.", ""]
    for schema, desc in SCHEMAS.items():
        objs = [k for k in objects if k[0] == schema]
        if not objs:
            continue
        out += [f"## `{schema}`: {desc}", ""]
        for (s, n, kind) in objs:
            full = f"{s}.{n}"
            rows_txt = f" · {counts[full]:,} rows" if counts.get(full, 0) > 0 else ""
            out += [f"### `{full}` ({kind}{rows_txt})", OBJECTS.get(full, "(no description yet)"), "",
                    "| Column | Type | Meaning |", "|---|---|---|"]
            out += [f"| `{c}` | {t} | {COLUMNS.get(c, '')} |" for c, t in objects[(s, n, kind)]]
            out.append("")
    OUT.write_text("\n".join(out), encoding="utf-8")
    print(f"{len(objects)} tables and views written to {OUT}")
    if missing:
        print("No description for: " + ", ".join(missing))


if __name__ == "__main__":
    main()
