"""Cleans the raw SAP-style extracts (data/raw) into data/clean, and logs every change.

Rules (each one counted in data/clean/cleaning_log.csv):
  C1  billing dates come in two formats (YYYY-MM-DD and SAP's DD.MM.YYYY): parse each format explicitly,
      never with automatic detection, which reads 2025-04-05 as 4 May when set to day-first
  C3  old material codes (OLD-xxxx): map to the current code from material_aliases
  C4  wire quantities entered in metres (unit M): convert to coils of 90 m
  C2  exact duplicate billing lines (same document, item and values): keep one. Runs after C1, C3 and C4,
      because a duplicate whose date or code was written differently only matches once both are normalised
  C5  customers with no region: take the region of their city from the other customers
After cleaning, totals are checked: rows in = rows out + rows removed, and net value is unchanged by C1, C3, C4.

    python src/clean_data.py
"""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
CLEAN = ROOT / "data" / "clean"
COIL_M = 90


def clean_billing(bill, alias, log):
    n0, value0 = len(bill), round(bill.net_value.sum(), 2)

    sap = bill.billing_date.str.contains(r"\.", regex=True)
    parsed = pd.Series(pd.NaT, index=bill.index, dtype="datetime64[ns]")
    parsed[~sap] = pd.to_datetime(bill.loc[~sap, "billing_date"], format="%Y-%m-%d")
    parsed[sap] = pd.to_datetime(bill.loc[sap, "billing_date"], format="%d.%m.%Y")
    assert parsed.notna().all(), "unparsed billing dates"
    bill["billing_date"] = parsed.dt.strftime("%Y-%m-%d")
    log.append(("C1", "billing", "Dates in DD.MM.YYYY converted to YYYY-MM-DD", int(sap.sum()), 0.0))

    old = bill.material.str.startswith("OLD-")
    bill.loc[old, "material"] = bill.loc[old, "material"].map(dict(zip(alias.old_material, alias.material)))
    assert bill.material.notna().all(), "old material code without a mapping"
    log.append(("C3", "billing", "Old material codes mapped to current codes", int(old.sum()), 0.0))

    m = bill.unit == "M"
    for col in ["quantity", "ordered_qty"]:
        bill.loc[m, col] = bill.loc[m, col] // COIL_M
    bill["unit"] = "EA"
    log.append(("C4", "billing", "Wire quantities in metres converted to 90 m coils", int(m.sum()), 0.0))

    # duplicates are only visible once dates, codes and units are consistent, so this runs last
    dup = bill.duplicated(keep="first")
    log.append(("C2", "billing", "Exact duplicate lines removed", int(dup.sum()), round(bill.loc[dup, "net_value"].sum(), 2)))
    bill = bill[~dup].copy()
    assert not bill.duplicated(["billing_doc", "item"]).any(), "document/item still not unique"

    assert len(bill) == n0 - int(dup.sum())
    assert abs(bill.net_value.sum() - (value0 - log[-1][4])) < 0.01
    return bill


def clean_customers(cust, log):
    city_region = cust.dropna(subset=["region"]).groupby("city").region.agg(lambda s: s.mode()[0])
    missing = cust.region.isna()
    cust.loc[missing, "region"] = cust.loc[missing, "city"].map(city_region)
    assert cust.region.notna().all(), "region could not be inferred for some customers"
    log.append(("C5", "customers", "Missing region taken from the customer's city", int(missing.sum()), 0.0))
    return cust


def main():
    CLEAN.mkdir(parents=True, exist_ok=True)
    log = []
    bill = pd.read_csv(RAW / "billing.csv", dtype={"billing_date": str})
    alias = pd.read_csv(RAW / "material_aliases.csv")
    cust = pd.read_csv(RAW / "customers.csv")
    bill = clean_billing(bill, alias, log)
    cust = clean_customers(cust, log)
    bill["reference_doc"] = bill.reference_doc.astype("Int64")   # read as float because invoices leave it blank
    bill.to_csv(CLEAN / "billing.csv", index=False)
    cust.to_csv(CLEAN / "customers.csv", index=False)
    for f in RAW.glob("*.csv"):                      # every other extract is used as received
        if f.name not in ("billing.csv", "customers.csv", "material_aliases.csv"):
            (CLEAN / f.name).write_bytes(f.read_bytes())
    pd.DataFrame(log, columns=["rule", "dataset", "action", "rows", "net_value_removed"]).to_csv(
        CLEAN / "cleaning_log.csv", index=False)
    for r in log:
        print(f"  {r[0]}  {r[2]:<52} {r[3]:>6} rows")
    print(f"Clean billing: {len(bill):,} lines. Written to data/clean.")


if __name__ == "__main__":
    main()
