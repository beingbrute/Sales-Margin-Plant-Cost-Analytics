"""The data loaded completely and every reporting layer agrees with the others."""
import pandas as pd
import pytest

from conftest import RAW


def test_clean_billing_is_raw_minus_duplicates(one):
    raw_rows = len(pd.read_csv(RAW / "billing.csv", usecols=["billing_doc"]))
    assert one("SELECT COUNT(*) FROM sd.billing") == raw_rows - one("SELECT rows FROM etl.cleaning_log WHERE rule = 'C2'")


@pytest.mark.parametrize("table,path", [("pp.production_orders", "production_orders.csv"),
                                        ("mm.stock_transfers", "stock_transfers.csv"),
                                        ("inp.field_notes", "field_notes.csv"), ("ref.customers", "customers.csv")])
def test_other_extracts_fully_loaded(one, table, path):
    assert one(f"SELECT COUNT(*) FROM {table}") == len(pd.read_csv(RAW / path))


def test_billing_ledger_and_views_agree_for_the_year(one):
    billing = float(one("SELECT SUM(net_value) FROM sd.billing"))
    assert float(one("SELECT SUM(net_sales) FROM rpt.sales_monthly")) == pytest.approx(billing, abs=1)
    assert float(one("SELECT SUM(revenue) FROM fi.gl_revenue")) == pytest.approx(billing, abs=1)


def test_standard_cost_is_the_sum_of_its_parts(one):
    assert one("SELECT COUNT(*) FROM ref.standard_costs "
               "WHERE abs(raw_material + conversion + packing - standard_cost) > 0.02") == 0


def test_margin_bridge_adds_up_in_every_row(query):
    df = query("SELECT * FROM rpt.margin_bridge")
    assert len(df) == 220
    assert ((df.volume + df.mix + df.price + df.cost + df.returns - df.change).abs() <= 5).all()


def test_regional_bridges_add_up_to_the_all_regions_change(query):
    df = query("SELECT month, category, scope = 'All' AS is_all, SUM(change) AS change FROM rpt.margin_bridge "
               "GROUP BY 1, 2, 3")
    p = df.pivot_table(index=["month", "category"], columns="is_all", values="change")
    assert ((p[True] - p[False]).abs() <= 5).all()


def test_no_line_runs_above_capacity(one):
    """A physical limit: the first version of the data broke it (utilisation up to 1,363%)."""
    assert one("SELECT MAX(utilisation_pct) FROM rpt.plant_cost") <= 100


def test_register_values_tie_to_their_source_views(one):
    r3 = one("SELECT value_inr FROM rpt.risk_opportunity WHERE id = 'R3'")
    src = one("SELECT (SELECT SUM(margin_lost) FROM rpt.short_shipments WHERE region = 'North') "
              "+ (SELECT SUM(extra_freight) FROM rpt.extra_freight WHERE to_warehouse = 'WN')")
    assert float(r3) == pytest.approx(float(src), abs=1)
    o1 = one("SELECT value_inr FROM rpt.risk_opportunity WHERE id = 'O1'")
    assert float(o1) == pytest.approx(float(one("SELECT SUM(leakage) FROM rpt.discount_leakage")), abs=1)
