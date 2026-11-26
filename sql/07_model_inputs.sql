-- =====================================================================
-- 07  Inputs for the Excel business case (exported by src/export_reporting.py)
-- =====================================================================

-- Water heaters made at Haridwar (WH-L1): North demand, where it was supplied from, East demand on Haridwar,
-- and the line's hours per unit, downtime and freight per unit by lane, by month
CREATE OR REPLACE VIEW rpt.wh_supply_monthly AS
WITH s AS (
    SELECT month,
           SUM(ordered_qty) FILTER (WHERE region = 'North')                     AS north_ordered,
           SUM(quantity) FILTER (WHERE region = 'North' AND plant = 'HDW')      AS north_from_haridwar,
           SUM(quantity) FILTER (WHERE region = 'North' AND plant = 'HSR')      AS north_from_hosur,
           SUM(ordered_qty - quantity) FILTER (WHERE region = 'North')          AS north_short,
           SUM(quantity) FILTER (WHERE region = 'East' AND plant = 'HDW')       AS east_from_haridwar,
           SUM(net_value - cost_at_standard) FILTER (WHERE region = 'North')
             / NULLIF(SUM(quantity) FILTER (WHERE region = 'North'), 0)          AS north_margin_per_unit,
           SUM(cost_at_standard) FILTER (WHERE region = 'North')
             / NULLIF(SUM(quantity) FILTER (WHERE region = 'North'), 0)          AS north_std_cost_per_unit
    FROM rpt.sales_lines WHERE billing_type = 'F2' AND category = 'Water heaters'
    GROUP BY month
), f AS (
    SELECT month,
           MAX(freight_per_unit) FILTER (WHERE from_plant = 'HDW') AS freight_haridwar_to_north,
           MAX(freight_per_unit) FILTER (WHERE from_plant = 'HSR') AS freight_hosur_to_north
    FROM rpt.lane_freight WHERE category = 'Water heaters' AND to_warehouse = 'WN' GROUP BY month
)
SELECT s.month, s.north_ordered, s.north_from_haridwar, COALESCE(s.north_from_hosur, 0) AS north_from_hosur,
       s.north_short, s.east_from_haridwar,
       round(s.north_margin_per_unit, 2) AS north_margin_per_unit, round(s.north_std_cost_per_unit, 2) AS north_std_cost_per_unit,
       p.units AS haridwar_units_made, p.machine_hours AS haridwar_hours_used,
       round(p.machine_hours / p.units, 6) AS hours_per_unit, p.available_hours, p.downtime_days,
       f.freight_haridwar_to_north, f.freight_hosur_to_north
FROM s
JOIN rpt.plant_cost p ON p.month = s.month AND p.line = 'WH-L1'
LEFT JOIN f ON f.month = s.month;

-- Wires by month: net sales, cost at standard and the copper part of it (for the copper and price what-if)
CREATE OR REPLACE VIEW rpt.wire_cost_monthly AS
SELECT s.month, SUM(s.quantity) AS units, round(SUM(s.net_value), 0) AS net_sales,
       round(SUM(s.cost_at_standard), 0) AS cost_at_standard,
       round(SUM(s.quantity * b.copper_kg * c.copper_per_kg), 0) AS copper_cost,
       c.copper_per_kg
FROM rpt.sales_lines s
JOIN ref.bill_of_materials b USING (material)
JOIN ref.commodity_prices c ON c.month = s.month
WHERE s.category = 'Wires' AND s.billing_type = 'F2'
GROUP BY s.month, c.copper_per_kg;
