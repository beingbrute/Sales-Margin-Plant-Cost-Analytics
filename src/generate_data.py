"""Generates the synthetic SAP-style extracts for Orvane Electricals (fictional), FY 2025-26.

Writes data/raw/*.csv (deliberately messy, like real ERP extracts) and
data/answer_key/expected_findings.csv (used only by the tests).
Every planted problem is listed in docs/design.md, section 4.

    python src/generate_data.py
"""
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 2026
rng = np.random.default_rng(SEED)
ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
KEY = ROOT / "data" / "answer_key"

MONTHS = pd.period_range("2025-04", "2026-03", freq="M")
MI = {str(m): i for i, m in enumerate(MONTHS)}          # month -> index 0..11 (Apr = 0)

# ---------------------------------------------------------------- reference data
PLANTS = pd.DataFrame([
    ("HDW", "Haridwar plant", "Haridwar", "North"),
    ("BDI", "Baddi plant", "Baddi", "North"),
    ("HSR", "Hosur plant", "Hosur", "South"),
], columns=["plant", "plant_name", "city", "zone"])

LINES = pd.DataFrame([            # fixed cost per month is set in production() from each line's volume
    ("HDW", "FAN-L1", "Fans"), ("HDW", "FAN-L2", "Fans"), ("HDW", "WH-L1", "Water heaters"),
    ("BDI", "STB-L1", "Stabilisers"), ("BDI", "STB-L2", "Stabilisers"),
    ("HSR", "WIR-L1", "Wires"), ("HSR", "WIR-L2", "Wires"), ("HSR", "WH-L2", "Water heaters"),
], columns=["plant", "line", "category"])

WAREHOUSES = pd.DataFrame([
    ("WN", "North warehouse", "Gurugram", "North"), ("WS", "South warehouse", "Bengaluru", "South"),
    ("WE", "East warehouse", "Kolkata", "East"), ("WW", "West warehouse", "Bhiwandi", "West"),
], columns=["warehouse", "warehouse_name", "city", "region"])
REGION_WH = dict(zip(WAREHOUSES.region, WAREHOUSES.warehouse))

# road distance plant -> warehouse (km), used for freight
DIST = {("HDW", "WN"): 230, ("HDW", "WS"): 2300, ("HDW", "WE"): 1450, ("HDW", "WW"): 1650,
        ("BDI", "WN"): 300, ("BDI", "WS"): 2350, ("BDI", "WE"): 1600, ("BDI", "WW"): 1700,
        ("HSR", "WN"): 2250, ("HSR", "WS"): 45, ("HSR", "WE"): 1900, ("HSR", "WW"): 1050}
FREIGHT_PER_KG_KM = 0.0042          # INR per kg per km, plant to warehouse

CHANNELS = ["Distributor", "Modern retail", "E-commerce", "Institutional"]
POLICY = {"Distributor": 12.0, "Modern retail": 8.0, "E-commerce": 15.0, "Institutional": 10.0}
REGIONS = ["North", "South", "East", "West"]

# commodity prices INR/kg: copper rises about 18% Jul-Sep (planted)
COPPER = [780, 785, 790, 845, 900, 921, 915, 912, 905, 900, 898, 895]
STEEL = [64, 64, 65, 65, 66, 66, 66, 65, 65, 65, 64, 64]
PLASTIC = [118, 119, 120, 120, 121, 121, 122, 122, 121, 121, 120, 120]

SEASON = {  # Apr..Mar
    "Fans": [1.55, 1.65, 1.30, 0.90, 0.80, 0.80, 0.70, 0.60, 0.60, 0.70, 1.00, 1.30],
    "Water heaters": [0.50, 0.40, 0.40, 0.50, 0.60, 0.80, 1.20, 1.60, 1.80, 1.60, 1.10, 0.70],
    "Wires": [0.90, 0.90, 0.85, 0.85, 0.90, 1.00, 1.05, 1.10, 1.10, 1.10, 1.15, 1.20],
    "Stabilisers": [1.30, 1.40, 1.20, 1.00, 0.90, 0.90, 0.90, 0.85, 0.85, 0.85, 0.90, 1.10],
}


def materials():
    rows = []
    def add(cat, seg, desc, price, cu, st, pl, conv, pack, plant, line, hours, kg):
        n = sum(r[2] == cat for r in rows) + 1
        prefix = {"Fans": "FN", "Wires": "WR", "Water heaters": "WH", "Stabilisers": "ST"}[cat]
        rows.append((f"{prefix}{n:03d}", desc, cat, seg, price, cu, st, pl, conv, pack, plant, line, hours, kg))
    for i, (seg, p) in enumerate([("Economy", 1450), ("Economy", 1550), ("Economy", 1650), ("Economy", 1700),
                                  ("Economy", 1800), ("Economy", 1850), ("Economy", 1900), ("Economy", 2000),
                                  ("Mid", 2600), ("Mid", 2800), ("Mid", 3000), ("Mid", 3200), ("Mid", 3350), ("Mid", 3500),
                                  ("Premium", 4800), ("Premium", 5400), ("Premium", 5900), ("Premium", 6400)]):
        bldc = seg == "Premium" and i >= 16
        desc = f"{'BLDC ' if bldc else ''}{seg} ceiling fan {1200 if i % 3 else 900}mm"
        cu = 0.32 + 0.12 * (seg != "Economy") + 0.05 * (seg == "Premium")
        conv = {"Economy": 260, "Mid": 340, "Premium": 520}[seg]
        add("Fans", seg, desc, p, cu, 1.6, 0.5, conv, 45, "HDW", "FAN-L1" if i % 2 else "FAN-L2",
            0.012 + 0.004 * (seg == "Premium"), 5.0)
    for i, (sz, cu) in enumerate([(1.0, 0.85), (1.5, 1.25), (2.5, 2.05), (4.0, 3.25), (6.0, 4.9), (10.0, 8.1)] * 3):
        if len(rows) >= 18 + 16:
            break
        grade = ["Standard", "FR", "FR-LSH"][i // 6]
        price = round(cu * 780 / 0.64 * (1 + 0.06 * (i // 6)), -1)
        add("Wires", "Mid" if grade == "Standard" else "Premium", f"{grade} PVC wire {sz} sq mm, 90 m", price,
            cu, 0.0, 0.35, 60 + 8 * (i // 6), 18, "HSR", "WIR-L1" if i % 2 else "WIR-L2", 0.006, cu + 0.5)
    for i, (seg, ltr, p) in enumerate([("Economy", 10, 6200), ("Economy", 15, 7000), ("Economy", 25, 8100),
                                       ("Mid", 10, 7900), ("Mid", 15, 8800), ("Mid", 25, 10200), ("Mid", 35, 12100),
                                       ("Premium", 15, 11800), ("Premium", 25, 13600), ("Premium", 35, 15400)]):
        add("Water heaters", seg, f"{seg} storage water heater {ltr} L", p, 0.3, 5 + ltr * 0.2, 1.1,
            {"Economy": 900, "Mid": 1150, "Premium": 1500}[seg], 160, "HDW+HSR", "WH-L1/WH-L2", 0.05, 8 + ltr * 0.25)
    for i, (seg, kva, p) in enumerate([("Economy", 2, 2100), ("Economy", 3, 2500), ("Economy", 4, 2900),
                                       ("Mid", 3, 3300), ("Mid", 4, 3700), ("Mid", 5, 4300),
                                       ("Premium", 4, 4900), ("Premium", 5, 5600)]):
        add("Stabilisers", seg, f"{seg} voltage stabiliser {kva} kVA", p, 0.7 + 0.2 * kva, 1.8, 0.3,
            {"Economy": 330, "Mid": 420, "Premium": 560}[seg], 55, "BDI", "STB-L1" if i % 2 == 0 else "STB-L2", 0.03, 4 + kva)
    df = pd.DataFrame(rows, columns=["material", "description", "category", "segment", "list_price",
                                     "copper_kg", "steel_kg", "plastic_kg", "conversion_std", "packing",
                                     "plant", "line", "machine_hours_per_unit", "weight_kg"])
    # Standard cost as a share of list price (at April commodity prices), split into raw material,
    # conversion and packing; raw material split into copper, steel and plastics by category.
    ratio = {("Fans", "Economy"): 0.70, ("Fans", "Mid"): 0.63, ("Fans", "Premium"): 0.57,
             ("Water heaters", "Economy"): 0.69, ("Water heaters", "Mid"): 0.62, ("Water heaters", "Premium"): 0.56,
             ("Stabilisers", "Economy"): 0.69, ("Stabilisers", "Mid"): 0.63, ("Stabilisers", "Premium"): 0.58,
             ("Wires", "Mid"): 0.75, ("Wires", "Premium"): 0.72}
    rm_share = {"Fans": 0.60, "Water heaters": 0.62, "Stabilisers": 0.62, "Wires": 0.88}
    mix = {"Fans": (0.40, 0.40, 0.20), "Water heaters": (0.15, 0.70, 0.15),
           "Stabilisers": (0.55, 0.35, 0.10), "Wires": (0.95, 0.0, 0.05)}       # copper, steel, plastics
    df[["copper_kg", "steel_kg", "plastic_kg", "conversion_std", "packing"]] = \
        df[["copper_kg", "steel_kg", "plastic_kg", "conversion_std", "packing"]].astype(float)
    for i, r in df.iterrows():
        cost = r.list_price * ratio[(r.category, r.segment)]
        rm = cost * rm_share[r.category]
        cu, stl, pl = mix[r.category]
        df.at[i, "copper_kg"] = round(rm * cu / COPPER[0], 3)
        df.at[i, "steel_kg"] = round(rm * stl / STEEL[0], 3)
        df.at[i, "plastic_kg"] = round(rm * pl / PLASTIC[0], 3)
        df.at[i, "packing"] = round(cost * 0.04, 2)
        df.at[i, "conversion_std"] = round(cost - rm - cost * 0.04, 2)
    return df


MAT = materials()
WH_MODEL_RETURNS = "WH006"          # the Hosur model with the planted quality issue (Mid 25 L)


def std_cost(m, mi):
    """Standard cost per unit for month index mi: raw material at that month's commodity prices."""
    rm = m.copper_kg * COPPER[mi] + m.steel_kg * STEEL[mi] + m.plastic_kg * PLASTIC[mi]
    return round(rm, 2), round(rm + m.conversion_std + m.packing, 2)


def price_list():
    rows = []
    for m in MAT.itertuples():
        rows.append((m.material, "2025-04-01", m.list_price))
        if m.category == "Wires":                       # planted: wire prices raised only in October
            rows.append((m.material, "2025-10-01", round(m.list_price * 1.12, -1)))
    return pd.DataFrame(rows, columns=["material", "valid_from", "list_price"])


PRICES = price_list()
PLANT_OF = dict(zip(MAT.material, MAT.plant))
STD = {(m.material, mi): std_cost(m, mi)[1] for m in MAT.itertuples() for mi in range(12)}


_PRICE_VERSIONS = {m: sorted(zip(g.valid_from, g.list_price)) for m, g in PRICES.groupby("material")}


def price_at(material, date):
    return float([p for d, p in _PRICE_VERSIONS[material] if d <= date][-1])


def customers():
    rows = []
    n = {"Distributor": 220, "Modern retail": 60, "E-commerce": 20, "Institutional": 100}
    cities = {"North": ["Delhi", "Gurugram", "Noida", "Jaipur", "Lucknow", "Chandigarh", "Dehradun"],
              "South": ["Bengaluru", "Chennai", "Hyderabad", "Kochi", "Coimbatore", "Mysuru"],
              "East": ["Kolkata", "Patna", "Bhubaneswar", "Guwahati", "Ranchi"],
              "West": ["Mumbai", "Pune", "Ahmedabad", "Surat", "Nagpur", "Indore"]}
    k = 0
    for ch, cnt in n.items():
        for _ in range(cnt):
            k += 1
            reg = REGIONS[rng.choice(4, p=[0.32, 0.27, 0.16, 0.25])]
            rows.append((f"C{k:05d}", f"{ch[:3].upper()} customer {k:03d}", ch, reg, rng.choice(cities[reg])))
    return pd.DataFrame(rows, columns=["customer", "customer_name", "channel", "region", "city"])


CUST = customers()

# ---------------------------------------------------------------- billing


def segment_weights(cat, region, mi):
    if cat == "Fans":
        w = {"Economy": 0.45, "Mid": 0.38, "Premium": 0.17}
        if region == "South" and mi <= 2:               # planted summer mix shift
            w = {"Economy": 0.66, "Mid": 0.26, "Premium": 0.08}
        if region == "West" and mi >= 4:                # planted competitor BLDC pressure on premium fans
            w = {"Economy": 0.49, "Mid": 0.42, "Premium": 0.09}
        return w
    if cat == "Wires":
        return {"Mid": 0.62, "Premium": 0.38}
    return {"Economy": 0.40, "Mid": 0.42, "Premium": 0.18}


CAT_MIX = {"Distributor": {"Fans": 0.33, "Wires": 0.35, "Water heaters": 0.17, "Stabilisers": 0.15},
           "Modern retail": {"Fans": 0.40, "Wires": 0.05, "Water heaters": 0.30, "Stabilisers": 0.25},
           "E-commerce": {"Fans": 0.45, "Wires": 0.03, "Water heaters": 0.30, "Stabilisers": 0.22},
           "Institutional": {"Fans": 0.25, "Wires": 0.55, "Water heaters": 0.10, "Stabilisers": 0.10}}
LINES_PER_MONTH = {"Distributor": 36, "Modern retail": 30, "E-commerce": 95, "Institutional": 10}
QTY = {"Distributor": (20, 80), "Modern retail": (8, 30), "E-commerce": (2, 10), "Institutional": (30, 150)}
FREIGHT_OUT = {"Distributor": 0.012, "Modern retail": 0.016, "E-commerce": 0.055, "Institutional": 0.010}  # share of net value


def billing():
    rows = []
    doc = 90_000_000
    mats_by = {(c, s): MAT[(MAT.category == c) & (MAT.segment == s)].material.tolist()
               for c in MAT.category.unique() for s in MAT.segment.unique()}
    for mi, per in enumerate(MONTHS):
        days = pd.date_range(per.start_time, per.end_time.normalize(), freq="D")
        ecom_growth = 0.75 + 0.06 * mi                  # planted: e-commerce grows through the year
        for c in CUST.itertuples():
            lam = LINES_PER_MONTH[c.channel] * (ecom_growth if c.channel == "E-commerce" else 1.0)
            lam *= np.mean([SEASON[k][mi] * v for k, v in CAT_MIX[c.channel].items()]) / 0.25
            n_lines = rng.poisson(lam)
            if n_lines == 0:
                continue
            n_docs = max(1, n_lines // 6)
            doc_ids = [doc + i for i in range(1, n_docs + 1)]
            doc += n_docs
            doc_dates = rng.choice(days, n_docs)
            cats = list(CAT_MIX[c.channel])
            cw = np.array([CAT_MIX[c.channel][k] * SEASON[k][mi] for k in cats]); cw /= cw.sum()
            for j in range(n_lines):
                d = j % n_docs
                cat = cats[rng.choice(4, p=cw)]
                sw = segment_weights(cat, c.region, mi)
                seg = list(sw)[rng.choice(len(sw), p=np.array(list(sw.values())) / sum(sw.values()))]
                mat = rng.choice(mats_by[(cat, seg)])
                lo, hi = QTY[c.channel]
                qty = int(rng.integers(lo, hi + 1))
                date = pd.Timestamp(doc_dates[d]).strftime("%Y-%m-%d")
                lp = price_at(mat, date)
                pol = POLICY[c.channel]
                disc = round(float(rng.uniform(0.35, 0.95)) * pol, 1)
                if c.channel == "Distributor" and c.region == "East" and 6 <= mi <= 8:
                    disc = round(float(rng.uniform(14.5, 19.0)), 1)   # planted: above the 12% policy
                ordered = qty
                plant = PLANT_OF[mat]
                if plant == "HDW+HSR":
                    plant = "HDW" if c.region in ("North", "East") else "HSR"
                    if c.region == "North" and 6 <= mi <= 9:          # planted: HDW shortfall, North served from Hosur
                        if rng.random() < 0.6:
                            plant = "HSR"
                        if rng.random() < 0.25:
                            qty = max(1, int(qty * rng.uniform(0.5, 0.85)))   # short shipment
                gross = qty * lp
                net = round(gross * (1 - disc / 100), 2)
                sc = STD[(mat, mi)]
                freight = round(net * FREIGHT_OUT[c.channel] * float(rng.uniform(0.85, 1.15)), 2)
                rows.append(("F2", doc_ids[d], date, c.customer, mat, plant, ordered, qty, lp, disc,
                             round(gross, 2), net, round(qty * sc, 2), freight, None))
    bill = pd.DataFrame(rows, columns=["billing_type", "billing_doc", "billing_date", "customer", "material",
                                       "plant", "ordered_qty", "quantity", "list_price", "discount_pct",
                                       "gross_value", "net_value", "cost_at_standard", "freight", "reference_doc"])
    bill.insert(2, "item", bill.groupby("billing_doc").cumcount().add(1) * 10)
    return bill


def credit_notes(bill):
    """Returns (G2 credit notes): under 1% of units normally; WH006 from Hosur about 9% in Jan-Feb (planted)."""
    b = bill.copy()
    b["month"] = b.billing_date.str[:7]
    planted = (b.material == WH_MODEL_RETURNS) & (b.plant == "HSR") & b.month.isin(["2026-01", "2026-02"])
    hit = rng.random(len(b)) < np.where(planted, 0.30, 0.03)
    cn = b[hit].copy()
    cn["quantity"] = np.maximum(1, (cn.quantity * rng.uniform(0.1, 0.4, len(cn))).round().astype(int))
    ratio = cn.quantity / b.loc[cn.index, "quantity"]
    for col in ["gross_value", "net_value", "cost_at_standard"]:
        cn[col] = -(b.loc[cn.index, col] * ratio).round(2)
    cn["freight"] = 0.0
    cn["ordered_qty"] = 0
    cn["quantity"] = -cn.quantity
    cn["reference_doc"] = cn.billing_doc
    cn["billing_type"] = "G2"
    shift = rng.integers(5, 25, len(cn))
    new_date = pd.to_datetime(cn.billing_date) + pd.to_timedelta(shift, unit="D")
    cn["billing_date"] = new_date.clip(upper=pd.Timestamp("2026-03-31")).dt.strftime("%Y-%m-%d")
    cn["billing_doc"] = np.arange(95_000_001, 95_000_001 + len(cn))
    cn["item"] = 10
    return cn.drop(columns="month")


# ---------------------------------------------------------------- production, capacity, stock


AVAILABLE_HOURS = 26 * 24          # 26 working days, 3 shifts
FIXED_SHARE = 0.55                 # share of standard conversion cost that is fixed (rent, salaried staff, depreciation)


def production(bill):
    """Production orders per line, product and month.

    Each line's fixed cost is set so that at its average monthly volume, actual conversion cost per unit equals
    standard: fixed cost is spread over the units made, so a quiet month costs more per unit and a busy one less.
    Machine hours per unit are set so the busiest normal month uses about 85% of available hours.
    """
    b = bill[bill.billing_type == "F2"].copy()
    b["mi"] = b.billing_date.str[:7].map(MI)
    demand = b.groupby(["mi", "material", "plant"]).quantity.sum().reset_index()
    m = MAT.set_index("material")

    plan = []                                         # (mi, line, plant, material, planned, actual, days_down)
    for mi in range(12):
        dm = demand[demand.mi == mi]
        for ln in LINES.itertuples():
            if ln.category == "Water heaters":
                items = dm[(dm.material.str.startswith("WH")) & (dm.plant == ln.plant)]
            else:
                items = dm[dm.material.isin(MAT[MAT.line == ln.line].material)]
            days_down = 21 if (ln.line == "STB-L1" and mi == 7) else 0       # planted: Baddi line down 3 weeks in Nov
            if ln.line == "WH-L1" and 6 <= mi <= 9:
                days_down = 9                                              # Haridwar water heater shortfall Oct-Jan
            for it in items.itertuples():
                planned = int(it.quantity * float(rng.uniform(1.0, 1.06)))
                actual = int(planned * float(rng.uniform(0.96, 1.01)) * (26 - days_down) / 26)
                plan.append((mi, ln.line, ln.plant, it.material, planned, actual, days_down))
    plan = pd.DataFrame(plan, columns=["mi", "line", "plant", "material", "planned", "actual", "days_down"])
    plan["std_conv"] = plan.material.map(m.conversion_std) * plan.planned

    lines = LINES.copy()
    per_line = plan.groupby(["line", "mi"]).agg(std_conv=("std_conv", "sum"), planned=("planned", "sum"))
    lines["fixed_cost_month"] = lines.line.map(per_line.groupby("line").std_conv.mean() * FIXED_SHARE).round(-3)
    hours_per_unit = 0.85 * AVAILABLE_HOURS / per_line.groupby("line").planned.max()

    rows, order = [], 1_000_000
    for (mi, line), g in plan.groupby(["mi", "line"]):
        fixed = float(lines.loc[lines.line == line, "fixed_cost_month"].iloc[0])
        units = g.actual.sum()
        for r in g.itertuples():
            mm = m.loc[r.material]
            rm = (mm.copper_kg * COPPER[mi] * float(rng.uniform(0.99, 1.03))
                  + mm.steel_kg * STEEL[mi] * float(rng.uniform(0.99, 1.02))
                  + mm.plastic_kg * PLASTIC[mi]) * r.actual
            conv = fixed * r.actual / units + mm.conversion_std * (1 - FIXED_SHARE) * r.actual
            order += 1
            rows.append((order, r.plant, line, r.material, str(MONTHS[mi]), r.planned, r.actual,
                         round(rm, 2), round(r.actual * hours_per_unit[line], 1), round(conv, 2)))
    prod = pd.DataFrame(rows, columns=["production_order", "plant", "line", "material", "month", "planned_qty",
                                       "actual_qty", "actual_material_cost", "machine_hours", "actual_conversion_cost"])
    cap = (plan.groupby(["line", "mi"]).days_down.max().reset_index()
           .merge(lines[["plant", "line", "fixed_cost_month"]], on="line"))
    cap["month"] = cap.mi.map(lambda i: str(MONTHS[i]))
    cap["available_hours"] = AVAILABLE_HOURS
    cap = cap.rename(columns={"days_down": "downtime_days", "fixed_cost_month": "fixed_cost"})
    cap = cap[["plant", "line", "month", "available_hours", "downtime_days", "fixed_cost"]]
    return prod, cap, lines


def transfers_and_stock(bill):
    b = bill[bill.billing_type == "F2"].merge(CUST[["customer", "region"]], on="customer")
    b["month"] = b.billing_date.str[:7]
    flows = b.groupby(["month", "plant", "region", "material"]).quantity.sum().reset_index()
    m = MAT.set_index("material")
    rows, n = [], 4_500_000
    for f in flows.itertuples():
        wh = REGION_WH[f.region]
        shipments = 2 if f.quantity > 200 else 1
        for s in range(shipments):
            q = int(f.quantity / shipments)
            if q == 0:
                continue
            n += 1
            disp = pd.Timestamp(f.month + "-01") + pd.Timedelta(days=int(rng.integers(0, 25)))
            transit = max(1, DIST[(f.plant, wh)] // 450)
            freight = q * m.loc[f.material].weight_kg * DIST[(f.plant, wh)] * FREIGHT_PER_KG_KM * float(rng.uniform(0.9, 1.1))
            rows.append((n, f.plant, wh, f.material, q, disp.strftime("%Y-%m-%d"),
                         (disp + pd.Timedelta(days=int(transit))).strftime("%Y-%m-%d"), round(freight, 2)))
    sto = pd.DataFrame(rows, columns=["sto_no", "from_plant", "to_warehouse", "material", "quantity",
                                      "dispatch_date", "receipt_date", "freight_cost"])
    # month-end stock: about 20 days of next month's sales, lower in the North for water heaters Oct-Jan (planted)
    sales = b.groupby(["month", "region", "material"]).quantity.sum().reset_index()
    stock = []
    for s in sales.itertuples():
        days = float(rng.uniform(16, 24))
        if s.region == "North" and s.material.startswith("WH") and s.month in ("2025-10", "2025-11", "2025-12", "2026-01"):
            days = float(rng.uniform(4, 8))
        stock.append((REGION_WH[s.region], s.material, s.month, int(s.quantity / 30 * days)))
    stk = pd.DataFrame(stock, columns=["warehouse", "material", "month", "closing_qty"])
    return sto, stk


# ---------------------------------------------------------------- ledger, function inputs, field notes


def gl_revenue(bill):
    """Revenue as booked in the ledger: billing net value, except 214 invoices dated 28-31 Dec booked in January."""
    b = bill.merge(MAT[["material", "category"]], on="material")
    late = b[(b.billing_type == "F2") & (b.billing_date >= "2025-12-28") & (b.billing_date <= "2025-12-31")]
    docs = late.billing_doc.drop_duplicates().sample(214, random_state=SEED)
    b["posting_month"] = b.billing_date.str[:7]
    b.loc[b.billing_doc.isin(docs), "posting_month"] = "2026-01"
    gl = b.groupby(["posting_month", "category"]).net_value.sum().round(2).reset_index()
    gl.columns = ["fiscal_month", "category", "revenue"]
    moved = b[b.billing_doc.isin(docs)]
    return gl, docs, round(moved.net_value.sum(), 2)


def function_inputs(bill):
    b = bill[bill.billing_type == "F2"].merge(MAT[["material", "category"]], on="material")
    b["month"] = b.billing_date.str[:7]
    actual = b.groupby(["month", "category"]).quantity.sum()
    rows = []
    for (month, cat), q in actual.items():
        rows.append(("Sales", "Sales planning", "Unit sales forecast", f"{month}|{cat}",
                     int(q * float(rng.uniform(0.9, 1.12))), "units"))
    for ln in LINES.itertuples():
        for mi in range(12):
            # the plant team's plan shows the line fully available: it does not include the November breakdown
            rows.append(("Plants", f"{ln.plant} plant head", "Planned working days", f"{MONTHS[mi]}|{ln.line}", 26, "days"))
    for (p, w), km in DIST.items():
        rows.append(("Supply chain", "Logistics manager", "Freight rate", f"{p}|{w}", round(FREIGHT_PER_KG_KM * km, 3), "INR per kg"))
    for k, v in [("Copper price assumption Jul-Mar", 800), ("Standard conversion uplift", 0.0),
                 ("Planned wire price increase", 12.0)]:
        rows.append(("Finance", "Plant controller", k, "FY25-26", v, "INR/kg" if "Copper" in k else "%"))
    return pd.DataFrame(rows, columns=["function", "provided_by", "input", "key", "value", "unit"])


NOTE_THEMES = {   # {slots} are filled with varied details; list lengths and order must not change (see field_notes)
    "Competitor pricing": ["{who} says a competitor BLDC fan is selling about {pct}% cheaper than our {fan} range.",
                           "Customers asking for BLDC fans; competitor scheme gives {pct}% extra margin to dealers.",
                           "Lost an order for {qty} {fan} fans to a cheaper competitor BLDC model."],
    "Delivery delays": ["Water heater orders delivered {days} days late; {who} had to turn customers away.",
                        "Short supply of {wh} water heaters at the warehouse this week.",
                        "{who} complains part orders arrived, balance of {qty} units still pending after {days} days."],
    "Discount pressure": ["{who} asking for {pct}% additional discount to clear stock before season end.",
                          "Dealers comparing our trade discount with other brands; wants {pct}% more.",
                          "Scheme discount requested again for a bulk order of {qty} wire coils."],
    "Product quality": ["Customer returned a {wh} water heater: heating element failure.",
                        "{n} water heater units returned with thermostat issues this month.",
                        "Service calls up for the {wh} model, {n} complaints in two weeks."],
    "Demand and season": ["{prod} demand strong this month; {who} expects to reorder soon.",
                          "Wire demand steady from {n} ongoing housing projects nearby.",
                          "Stabiliser enquiries up after voltage fluctuations in the area."],
    "Display and visibility": ["{who} wants new display stands for the {prod} range.",
                               "Our products not visible in the store; competitor has the front shelf."],
    "Payment terms": ["{who} asking for {days} more days of credit.",
                      "Payment delayed by modern retail chain; awaiting their {days}-day cycle."],
}
# A second topic mentioned in about 1 note in 8, as real visit notes do; the note keeps its main theme
SECOND = {
    "Competitor pricing": "Also mentioned competitor prices are lower.",
    "Delivery delays": "Also said the last delivery came late.",
    "Discount pressure": "Also wants a better scheme.",
    "Product quality": "One customer complaint about a faulty unit too.",
    "Demand and season": "Says footfall is good this month.",
    "Display and visibility": "Asked again for posters and a display stand.",
    "Payment terms": "Also wants longer credit.",
}
CITIES = {"North": ["Delhi", "Noida", "Jaipur", "Lucknow", "Chandigarh"], "South": ["Bengaluru", "Chennai", "Hyderabad", "Kochi"],
          "East": ["Kolkata", "Patna", "Bhubaneswar", "Ranchi"], "West": ["Mumbai", "Pune", "Ahmedabad", "Surat", "Indore"]}
WHO = ["Retailer", "Dealer", "Distributor", "Store manager", "Shop owner"]
rng_notes = np.random.default_rng(SEED + 1)    # separate stream: varying the text does not change any other data


def note_text(template, theme, region):
    who = f"{rng_notes.choice(WHO)} in {rng_notes.choice(CITIES[region])}"
    text = template.format(who=who, pct=int(rng_notes.integers(5, 21)), days=int(rng_notes.integers(3, 31)),
                           qty=int(rng_notes.integers(20, 400)), n=int(rng_notes.integers(2, 12)),
                           fan=rng_notes.choice(["premium", "mid-range", "ceiling"]),
                           wh=rng_notes.choice(["15 L", "25 L", "35 L"]),
                           prod=rng_notes.choice(["Fan", "Wire", "Water heater", "Stabiliser"]))
    if rng_notes.random() < 0.125:
        other = rng_notes.choice([t for t in SECOND if t != theme])
        text += " " + SECOND[other]
    return text


def field_notes():
    rows = []
    for k in range(1, 1201):
        mi = int(rng.integers(0, 12))
        region = REGIONS[rng.choice(4)]
        channel = CHANNELS[rng.choice(4, p=[0.6, 0.2, 0.05, 0.15])]
        w = {t: 1.0 for t in NOTE_THEMES}
        if region == "West" and mi >= 4:
            w["Competitor pricing"] = 5.0             # planted theme
        if region == "North" and 6 <= mi <= 9:
            w["Delivery delays"] = 4.0
        if region == "East" and 6 <= mi <= 8:
            w["Discount pressure"] = 4.0
        if mi in (9, 10):
            w["Product quality"] = 3.0
        themes = list(w)
        p = np.array([w[t] for t in themes]); p /= p.sum()
        theme = themes[rng.choice(len(themes), p=p)]
        text = note_text(rng.choice(NOTE_THEMES[theme]), theme, region)
        day = int(rng.integers(1, 28))
        rows.append((f"N{k:05d}", f"{MONTHS[mi].year}-{MONTHS[mi].month:02d}-{day:02d}", region, channel, text, theme))
    notes = pd.DataFrame(rows, columns=["note_id", "visit_date", "region", "channel", "note", "theme_true"])
    return notes


# ---------------------------------------------------------------- make the extracts messy


def make_messy(bill, cust):
    """ERP extracts are rarely clean. Counts of each issue go to the answer key."""
    issues = {}
    dup = bill.sample(180, random_state=SEED)
    bill = pd.concat([bill, dup], ignore_index=True)
    issues["duplicate_billing_lines"] = 180
    old = {m: "OLD-" + m for m in MAT.material.sample(6, random_state=SEED)}
    mask = bill.material.isin(old) & (rng.random(len(bill)) < 0.15)
    bill.loc[mask, "material"] = bill.loc[mask, "material"].map(old)
    issues["old_material_codes"] = int(mask.sum())
    alias = pd.DataFrame({"old_material": list(old.values()), "material": list(old.keys())})
    sap_dates = rng.random(len(bill)) < 0.08
    d = pd.to_datetime(bill.loc[sap_dates, "billing_date"])
    bill.loc[sap_dates, "billing_date"] = d.dt.strftime("%d.%m.%Y")
    issues["dates_in_sap_format"] = int(sap_dates.sum())
    wires = bill.material.str.contains("WR") & (bill.billing_type == "F2")
    metres = wires & (rng.random(len(bill)) < 0.01)
    bill.loc[metres, "quantity"] = bill.loc[metres, "quantity"] * 90
    bill.loc[metres, "ordered_qty"] = bill.loc[metres, "ordered_qty"] * 90
    bill["unit"] = np.where(metres, "M", "EA")
    issues["wire_lines_in_metres"] = int(metres.sum())
    missing = cust.sample(25, random_state=SEED).index
    true_region = cust.loc[missing, ["customer", "region"]].copy()
    cust = cust.copy()
    cust.loc[missing, "region"] = None
    issues["customers_missing_region"] = 25
    return bill, cust, alias, issues, true_region


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    KEY.mkdir(parents=True, exist_ok=True)
    bill = billing()
    cn = credit_notes(bill)
    bill = pd.concat([bill, cn], ignore_index=True)
    prod, cap, lines = production(bill)
    sto, stk = transfers_and_stock(bill)
    gl, moved_docs, moved_value = gl_revenue(bill)
    inputs = function_inputs(bill)
    notes = field_notes()

    costs = []
    for m in MAT.itertuples():
        for mi in range(12):
            rm, total = std_cost(m, mi)
            costs.append((m.material, str(MONTHS[mi].start_time.date()), rm, m.conversion_std, m.packing, total))
    std = pd.DataFrame(costs, columns=["material", "valid_from", "raw_material", "conversion", "packing", "standard_cost"])
    comm = pd.DataFrame({"month": [str(p) for p in MONTHS], "copper_per_kg": COPPER,
                         "steel_per_kg": STEEL, "plastic_per_kg": PLASTIC})

    messy_bill, messy_cust, alias, issues, true_region = make_messy(bill, CUST)

    out = {
        "plants.csv": PLANTS, "lines.csv": lines, "warehouses.csv": WAREHOUSES,
        "materials.csv": MAT.drop(columns=["copper_kg", "steel_kg", "plastic_kg"]),
        "bill_of_materials.csv": MAT[["material", "copper_kg", "steel_kg", "plastic_kg"]],
        "material_aliases.csv": alias,
        "standard_costs.csv": std, "price_list.csv": PRICES,
        "discount_policy.csv": pd.DataFrame({"channel": list(POLICY), "max_discount_pct": list(POLICY.values())}),
        "customers.csv": messy_cust, "billing.csv": messy_bill,
        "production_orders.csv": prod, "plant_capacity.csv": cap,
        "stock_transfers.csv": sto, "warehouse_stock.csv": stk,
        "commodity_prices.csv": comm, "gl_revenue.csv": gl,
        "function_inputs.csv": inputs, "field_notes.csv": notes.drop(columns="theme_true"),
    }
    for name, df in out.items():
        df.to_csv(RAW / name, index=False)

    key = [
        ("DQ", "duplicate_billing_lines", issues["duplicate_billing_lines"], "rows"),
        ("DQ", "old_material_codes", issues["old_material_codes"], "rows"),
        ("DQ", "dates_in_sap_format", issues["dates_in_sap_format"], "rows"),
        ("DQ", "wire_lines_in_metres", issues["wire_lines_in_metres"], "rows"),
        ("DQ", "customers_missing_region", issues["customers_missing_region"], "customers"),
        ("REC", "cutoff_invoices_dec_to_jan", 214, "invoices"),
        ("REC", "cutoff_value_dec_to_jan", moved_value, "INR"),
        ("OPS", "copper_rise_jul_sep_pct", round((COPPER[5] / COPPER[0] - 1) * 100, 1), "%"),
        ("OPS", "wire_price_increase_oct_pct", 12.0, "%"),
        ("OPS", "south_fans_economy_share_apr_jun", 0.66, "share"),
        ("OPS", "east_distributor_discount_above_policy", "2025-10..2025-12", "months"),
        ("OPS", "baddi_stb_l1_downtime_days_nov", 21, "days"),
        ("OPS", "wh006_hosur_return_rate_jan_feb", 0.09, "share"),
        ("OPS", "north_water_heaters_from_hosur", "2025-10..2026-01", "months"),
        ("OPS", "west_premium_fan_share_from_aug", 0.09, "share"),
        ("OPS", "ecommerce_volume_growth", "rises through the year", ""),
    ]
    inv = bill[bill.billing_type == "F2"]
    jf = inv[(inv.material == WH_MODEL_RETURNS) & (inv.plant == "HSR") & inv.billing_date.str[:7].isin(["2026-01", "2026-02"])]
    ret = -cn[cn.reference_doc.isin(jf.billing_doc) & (cn.material == WH_MODEL_RETURNS)].quantity.sum()
    key = [k if k[1] != "wh006_hosur_return_rate_jan_feb" else (k[0], k[1], round(ret / jf.quantity.sum(), 4), k[3])
           for k in key]
    pd.DataFrame(key, columns=["type", "finding", "value", "unit"]).to_csv(KEY / "expected_findings.csv", index=False)
    true_region.to_csv(KEY / "customer_regions.csv", index=False)
    notes[["note_id", "theme_true"]].to_csv(KEY / "field_note_themes.csv", index=False)

    print(f"materials {len(MAT)}, customers {len(CUST)}, billing lines {len(messy_bill):,} "
          f"(invoices {int((bill.billing_type == 'F2').sum()):,}, credit notes {len(cn):,}), "
          f"production orders {len(prod):,}, stock transfers {len(sto):,}, field notes {len(notes):,}")
    print(f"net sales (clean) INR {bill.net_value.sum() / 1e7:,.1f} crore; cut-off moved INR {moved_value:,.0f}")


if __name__ == "__main__":
    main()
