-- =====================================================================
-- 05  Supply chain: freight by lane, fill rate, days of stock
-- =====================================================================

-- Plant to warehouse freight per unit by lane
CREATE OR REPLACE VIEW rpt.lane_freight AS
SELECT to_char(t.dispatch_date, 'YYYY-MM') AS month, t.from_plant, t.to_warehouse, m.category,
       SUM(t.quantity) AS units, round(SUM(t.freight_cost), 2) AS freight,
       round(SUM(t.freight_cost) / SUM(t.quantity), 2) AS freight_per_unit
FROM mm.stock_transfers t JOIN ref.materials m USING (material)
GROUP BY 1, 2, 3, 4;

-- Fill rate: invoiced quantity / ordered quantity (short shipments lower it)
CREATE OR REPLACE VIEW rpt.fill_rate AS
SELECT month, region, category, SUM(ordered_qty) AS ordered, SUM(quantity) AS shipped,
       round(100.0 * SUM(quantity) / SUM(ordered_qty), 2) AS fill_rate_pct
FROM rpt.sales_lines WHERE billing_type = 'F2'
GROUP BY month, region, category;

-- Days of stock at month end: closing stock / average daily sales in the month
CREATE OR REPLACE VIEW rpt.days_of_stock AS
WITH s AS (
    SELECT month, region, category, SUM(quantity) AS units_sold,
           EXTRACT(DAY FROM (to_date(month || '-01', 'YYYY-MM-DD') + INTERVAL '1 month - 1 day')) AS days
    FROM rpt.sales_lines WHERE billing_type = 'F2' GROUP BY 1, 2, 3
), k AS (
    SELECT w.month, h.region, m.category, SUM(w.closing_qty) AS closing_qty
    FROM mm.warehouse_stock w JOIN ref.warehouses h USING (warehouse) JOIN ref.materials m USING (material)
    GROUP BY 1, 2, 3
)
SELECT k.month, k.region, k.category, k.closing_qty, s.units_sold,
       round(k.closing_qty / (s.units_sold / s.days), 1) AS days_of_stock
FROM k JOIN s USING (month, region, category);

-- Extra freight when a warehouse is supplied from a plant other than its normal one:
-- units on the longer lane x (its freight per unit - the normal lane's freight per unit in the same month)
CREATE OR REPLACE VIEW rpt.extra_freight AS
WITH normal AS (   -- the plant that normally supplies each warehouse with each category: the one shipping the most units
    SELECT DISTINCT ON (to_warehouse, category) to_warehouse, category, from_plant AS normal_plant
    FROM rpt.lane_freight GROUP BY to_warehouse, category, from_plant
    ORDER BY to_warehouse, category, SUM(units) DESC
)
SELECT l.month, l.from_plant, l.to_warehouse, l.category, l.units, l.freight_per_unit,
       n2.freight_per_unit AS normal_freight_per_unit,
       round(l.units * (l.freight_per_unit - n2.freight_per_unit), 0) AS extra_freight
FROM rpt.lane_freight l
JOIN normal n ON n.to_warehouse = l.to_warehouse AND n.category = l.category AND n.normal_plant <> l.from_plant
JOIN rpt.lane_freight n2 ON n2.month = l.month AND n2.to_warehouse = l.to_warehouse
                        AND n2.category = l.category AND n2.from_plant = n.normal_plant;

-- Short shipments: units ordered but not shipped, valued at the line's net price and margin per unit
CREATE OR REPLACE VIEW rpt.short_shipments AS
SELECT month, region, category,
       SUM(ordered_qty - quantity)                                                        AS units_short,
       round(SUM((ordered_qty - quantity) * net_value / NULLIF(quantity, 0)), 0)          AS sales_lost,
       round(SUM((ordered_qty - quantity) * (net_value - cost_at_standard) / NULLIF(quantity, 0)), 0) AS margin_lost
FROM rpt.sales_lines WHERE billing_type = 'F2' AND ordered_qty > quantity
GROUP BY month, region, category;
