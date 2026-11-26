"""Every planted problem in the answer key (data/answer_key) is found by the SQL views, and nothing else is."""
import pandas as pd
import pytest

from conftest import KEY

FIND = pd.read_csv(KEY / "expected_findings.csv").set_index("finding").value


def key(name):
    return float(FIND[name])


@pytest.mark.parametrize("rule,finding", [("C1", "dates_in_sap_format"), ("C2", "duplicate_billing_lines"),
                                          ("C3", "old_material_codes"), ("C4", "wire_lines_in_metres"),
                                          ("C5", "customers_missing_region")])
def test_cleaning_fixes_exactly_the_planted_issues(one, rule, finding):
    assert one("SELECT rows FROM etl.cleaning_log WHERE rule = %s", (rule,)) == key(finding)


def test_missing_regions_inferred_correctly(query):
    truth = pd.read_csv(KEY / "customer_regions.csv").set_index("customer").region
    got = query("SELECT customer, region FROM ref.customers WHERE customer = ANY(%s)",
                (list(truth.index),)).set_index("customer").region
    assert (got.reindex(truth.index) == truth).all()


def test_copper_rise_hits_wire_margin_until_the_october_price_rise(query, one):
    cu = query("SELECT month, copper_per_kg FROM ref.commodity_prices").set_index("month").copper_per_kg
    assert (cu["2025-09"] / cu["2025-04"] - 1) * 100 == pytest.approx(key("copper_rise_jul_sep_pct"), abs=0.1)
    gm = query("SELECT month, gross_margin_pct FROM rpt.margin_by_category WHERE category = 'Wires'"
               ).set_index("month").gross_margin_pct
    assert gm["2025-09"] < 10 < 15 < gm["2025-10"]
    assert float(one("SELECT round(100 * (MAX(list_price) / MIN(list_price) - 1), 1) FROM ref.price_list "
                     "WHERE material = 'WR001'")) == pytest.approx(key("wire_price_increase_oct_pct"), abs=0.5)


def test_south_summer_fan_mix_shift(query):
    df = query("SELECT month, region, unit_share FROM rpt.segment_mix WHERE category = 'Fans' AND segment = 'Economy'")
    south_summer = df[(df.region == "South") & df.month.isin(["2025-04", "2025-05", "2025-06"])].unit_share
    rest = df[~((df.region == "South") & df.month.isin(["2025-04", "2025-05", "2025-06"]))].unit_share
    assert south_summer.mean() == pytest.approx(key("south_fans_economy_share_apr_jun"), abs=0.03)
    assert south_summer.min() > rest.max()


def test_discount_above_policy_only_east_distributors_oct_to_dec(query):
    df = query("SELECT month, region, channel, leakage FROM rpt.discount_leakage WHERE leakage > 0")
    assert set(df.region) == {"East"} and set(df.channel) == {"Distributor"}
    assert set(df.month) == {"2025-10", "2025-11", "2025-12"}


def test_baddi_breakdown_in_november(query):
    df = query("SELECT month, downtime_days, utilisation_pct, actual_cost_per_unit, std_cost_per_unit "
               "FROM rpt.plant_cost WHERE line = 'STB-L1'").set_index("month")
    nov = df.loc["2025-11"]
    assert nov.downtime_days == key("baddi_stb_l1_downtime_days_nov")
    assert nov.utilisation_pct < 15 < df.drop("2025-11").utilisation_pct.min()
    assert nov.actual_cost_per_unit > 1.8 * nov.std_cost_per_unit


def test_wh006_returns_from_hosur(query):
    df = query("SELECT invoice_month, SUM(units_returned) AS ret, SUM(units_invoiced) AS inv FROM rpt.return_rates "
               "WHERE material = 'WH006' AND plant = 'HSR' AND invoice_month IN ('2026-01', '2026-02') GROUP BY 1")
    assert df.ret.sum() / df.inv.sum() == pytest.approx(key("wh006_hosur_return_rate_jan_feb"), abs=0.0001)
    others = query("SELECT SUM(units_returned)::NUMERIC / SUM(units_invoiced) AS r FROM rpt.return_rates "
                   "WHERE NOT (material = 'WH006' AND plant = 'HSR')").r[0]
    assert others < 0.01


def test_north_water_heaters_from_hosur_only_in_winter(query):
    df = query("SELECT month, from_plant FROM rpt.lane_freight WHERE category = 'Water heaters' AND to_warehouse = 'WN'")
    assert set(df[df.from_plant == "HSR"].month) == {"2025-10", "2025-11", "2025-12", "2026-01"}
    fr = query("SELECT month, region, fill_rate_pct FROM rpt.fill_rate WHERE fill_rate_pct < 100")
    assert set(fr.region) == {"North"} and set(fr.month) == {"2025-10", "2025-11", "2025-12", "2026-01"}


def test_west_premium_fans_lose_share_from_august(query):
    df = query("SELECT month >= '2025-08' AS after, SUM(units) FILTER (WHERE segment = 'Premium')::NUMERIC / SUM(units) AS s "
               "FROM rpt.segment_mix WHERE region = 'West' AND category = 'Fans' GROUP BY 1").set_index("after").s
    assert df[True] == pytest.approx(key("west_premium_fan_share_from_aug"), abs=0.01)
    assert df[False] > 0.15


def test_ecommerce_gross_margin_fine_contribution_worst(query):
    df = query("SELECT * FROM rpt.margin_by_channel").set_index("channel")
    assert df.contribution_pct.idxmin() == "E-commerce"
    assert df.gross_margin_pct.rank(ascending=False)["E-commerce"] == 2
    units = query("SELECT month, units FROM rpt.channel_trend WHERE channel = 'E-commerce' ORDER BY month").units
    assert units.iloc[-1] > 1.5 * units.iloc[0]


def test_cutoff_moves_revenue_from_december_to_january(query):
    df = query("SELECT month, difference FROM rpt.reconciliation_summary").set_index("month").difference
    value = key("cutoff_value_dec_to_jan")
    assert df["2025-12"] == pytest.approx(-value, abs=1) and df["2026-01"] == pytest.approx(value, abs=1)
    assert (df.drop(["2025-12", "2026-01"]).abs() < 1).all()
