"""Recalculates key results in pandas from the raw extracts, with its own cleaning, without the SQL views or
src/clean_data.py. A mistake would have to be made twice, in two languages, to pass."""
import numpy as np
import pandas as pd
import pytest

from conftest import RAW


@pytest.fixture(scope="module")
def lines():
    b = pd.read_csv(RAW / "billing.csv", dtype={"billing_date": str})
    alias = dict(pd.read_csv(RAW / "material_aliases.csv")[["old_material", "material"]].values)
    sap = b.billing_date.str.contains(".", regex=False)
    b["date"] = pd.to_datetime(b.billing_date.where(~sap), format="%Y-%m-%d")
    b.loc[sap, "date"] = pd.to_datetime(b.loc[sap, "billing_date"], format="%d.%m.%Y")
    b["material"] = b.material.replace(alias)
    m = b.unit == "M"
    b.loc[m, ["quantity", "ordered_qty"]] = b.loc[m, ["quantity", "ordered_qty"]] // 90
    b = b.drop(columns=["billing_date", "unit"]).drop_duplicates()
    b["month"] = b.date.dt.strftime("%Y-%m")
    mat = pd.read_csv(RAW / "materials.csv")[["material", "category"]]
    cust = pd.read_csv(RAW / "customers.csv")
    city = cust.dropna(subset=["region"]).groupby("city").region.first()
    cust["region"] = cust.region.fillna(cust.city.map(city))
    return b.merge(mat, on="material").merge(cust[["customer", "channel", "region"]], on="customer")


def test_monthly_net_sales_and_margin(lines, query):
    mine = lines.groupby(["month", "category"]).agg(net=("net_value", "sum"), cost=("cost_at_standard", "sum"))
    mine["gm_pct"] = (100 * (mine.net - mine.cost) / mine.net).round(1)
    sql = query("SELECT month, category, net_sales, gross_margin_pct FROM rpt.margin_by_category").set_index(["month", "category"])
    assert np.allclose(mine.net.sort_index(), sql.net_sales.sort_index(), atol=1)
    assert np.allclose(mine.gm_pct.sort_index(), sql.gross_margin_pct.sort_index(), atol=0.051)


def test_wire_price_and_cost_effects(lines, query):
    w = lines[(lines.billing_type == "F2") & (lines.category == "Wires")]
    g = w.groupby(["month", "material"]).agg(u=("quantity", "sum"), n=("net_value", "sum"), c=("cost_at_standard", "sum"))
    for month, prev in [("2025-08", "2025-07"), ("2025-10", "2025-09")]:
        cur, old = g.loc[month], g.loc[prev]
        both = cur.index.intersection(old.index)
        price = (cur.u[both] * (cur.n[both] / cur.u[both] - old.n[both] / old.u[both])).sum()
        cost = -(cur.u[both] * (cur.c[both] / cur.u[both] - old.c[both] / old.u[both])).sum()
        sql = query("SELECT price, cost FROM rpt.margin_bridge WHERE scope = 'All' AND category = 'Wires' AND month = %s",
                    (month,)).iloc[0]
        assert price == pytest.approx(sql.price, abs=2) and cost == pytest.approx(sql.cost, abs=2)


def test_discount_above_policy(lines, one):
    pol = pd.read_csv(RAW / "discount_policy.csv").set_index("channel").max_discount_pct
    f = lines[lines.billing_type == "F2"]
    leak = (f.gross_value * (f.discount_pct - f.channel.map(pol)).clip(lower=0) / 100).sum()
    assert leak == pytest.approx(float(one("SELECT SUM(leakage) FROM rpt.discount_leakage")), abs=50)


def test_wh006_return_rate_by_invoice_month(lines, one):
    inv = lines[(lines.billing_type == "F2") & (lines.material == "WH006") & (lines.plant == "HSR")
                & lines.month.isin(["2026-01", "2026-02"])]
    cn = lines[(lines.billing_type == "G2") & lines.reference_doc.isin(inv.billing_doc) & (lines.material == "WH006")]
    mine = -cn.quantity.sum() / inv.quantity.sum()
    sql = one("SELECT SUM(units_returned)::NUMERIC / SUM(units_invoiced) FROM rpt.return_rates "
              "WHERE material = 'WH006' AND plant = 'HSR' AND invoice_month IN ('2026-01', '2026-02')")
    assert mine == pytest.approx(float(sql), abs=1e-6)
