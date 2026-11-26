"""
Create the `orvane` database, build the schema and views, and load the cleaned extracts.

  1. creates the database if it does not exist
  2. runs every sql/*.sql script in order (schema first, then the views)
  3. loads data/clean with COPY (run src/clean_data.py first)

    python src/load_data.py --port 5432
"""
import argparse
import sys
from pathlib import Path

from db import DB_NAME, add_connection_args, connect

ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "data" / "clean"
SQL = ROOT / "sql"

FILES = [  # parents before children
    ("ref.plants", "plants.csv"), ("ref.lines", "lines.csv"), ("ref.warehouses", "warehouses.csv"),
    ("ref.materials", "materials.csv"), ("ref.bill_of_materials", "bill_of_materials.csv"),
    ("ref.standard_costs", "standard_costs.csv"), ("ref.price_list", "price_list.csv"),
    ("ref.discount_policy", "discount_policy.csv"), ("ref.customers", "customers.csv"),
    ("ref.commodity_prices", "commodity_prices.csv"),
    ("sd.billing", "billing.csv"),
    ("pp.production_orders", "production_orders.csv"), ("pp.plant_capacity", "plant_capacity.csv"),
    ("mm.stock_transfers", "stock_transfers.csv"), ("mm.warehouse_stock", "warehouse_stock.csv"),
    ("fi.gl_revenue", "gl_revenue.csv"),
    ("inp.function_inputs", "function_inputs.csv"), ("inp.field_notes", "field_notes.csv"),
    ("etl.cleaning_log", "cleaning_log.csv"),
]


def main():
    p = argparse.ArgumentParser()
    add_connection_args(p)
    args = p.parse_args()
    if not (CLEAN / "billing.csv").exists():
        print("ERROR: data/clean not found. Run: python src/generate_data.py, then python src/clean_data.py")
        sys.exit(2)

    con = connect(args, "postgres")
    con.autocommit = True
    with con.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (DB_NAME,))
        if cur.fetchone() is None:
            cur.execute(f"CREATE DATABASE {DB_NAME}")
            print(f"Created database {DB_NAME}")
    con.close()

    con = connect(args)
    with con, con.cursor() as cur:
        scripts = sorted(SQL.glob("*.sql"))
        for f in scripts:
            cur.execute(f.read_text(encoding="utf-8"))
        for table, name in FILES:
            with open(CLEAN / name, encoding="utf-8") as fh:
                header = fh.readline().strip()
                cur.copy_expert(f"COPY {table} ({header}) FROM STDIN WITH (FORMAT csv)", fh)
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            print(f"  {table:<24} {cur.fetchone()[0]:>8,} rows")
        tagged = ROOT / "data" / "derived" / "field_note_themes_llm.csv"
        if tagged.exists():                          # written by src/tag_field_notes.py
            with open(tagged, encoding="utf-8") as fh:
                header = fh.readline().strip()
                cur.copy_expert(f"COPY inp.field_note_themes ({header}) FROM STDIN WITH (FORMAT csv)", fh)
            cur.execute("SELECT COUNT(*) FROM inp.field_note_themes")
            print(f"  {'inp.field_note_themes':<24} {cur.fetchone()[0]:>8,} rows")
        else:
            print("  inp.field_note_themes: not loaded yet (run src/tag_field_notes.py)")
        cur.execute("SELECT schemaname || '.' || matviewname FROM pg_matviews WHERE schemaname = 'rpt' ORDER BY 1")
        for (mv,) in cur.fetchall():
            cur.execute(f"REFRESH MATERIALIZED VIEW {mv}")
            print(f"  refreshed {mv}")
    con.close()
    print(f"Ran {len(scripts)} SQL script(s). Done.")


if __name__ == "__main__":
    main()
