"""Exports the reporting views to reporting/*.csv (read by the Excel business case and the review pack).

    python src/export_reporting.py --port 5432
"""
import argparse
import csv
from pathlib import Path

from db import add_connection_args, connect

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reporting"
VIEWS = ["sales_monthly", "margin_by_category", "margin_by_channel", "margin_bridge", "discount_leakage",
         "plant_cost", "return_rates", "lane_freight", "extra_freight", "short_shipments", "fill_rate",
         "days_of_stock", "reconciliation_summary", "risk_opportunity", "wh_supply_monthly", "wire_cost_monthly"]


def main():
    p = argparse.ArgumentParser()
    add_connection_args(p)
    args = p.parse_args()
    OUT.mkdir(exist_ok=True)
    con = connect(args)
    with con.cursor() as cur:
        for v in VIEWS:
            cur.execute(f"SELECT * FROM rpt.{v} ORDER BY 1, 2")
            rows = cur.fetchall()
            with open(OUT / f"{v}.csv", "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow([d[0] for d in cur.description])
                w.writerows(rows)
            print(f"  {v:<24} {len(rows):>6} rows")
    con.close()
    print(f"Exported {len(VIEWS)} views to reporting/")


if __name__ == "__main__":
    main()
