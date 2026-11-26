-- =====================================================================
-- 04  Plants: cost per unit, actual vs standard, utilisation, and returns by plant
-- =====================================================================

-- Actual vs standard cost by production line and month.
--   standard material  = units produced x raw material cost in that month's standard cost estimate
--   standard conversion = units produced x standard conversion cost per unit
-- A variance above zero means the line cost more than standard.
CREATE OR REPLACE VIEW rpt.plant_cost AS
WITH o AS (
    SELECT p.plant, p.line, p.month, p.material, p.actual_qty, p.planned_qty, p.machine_hours,
           p.actual_material_cost, p.actual_conversion_cost,
           p.actual_qty * s.raw_material AS std_material, p.actual_qty * s.conversion AS std_conversion
    FROM pp.production_orders p
    JOIN ref.standard_costs s ON s.material = p.material AND s.valid_from = to_date(p.month || '-01', 'YYYY-MM-DD')
)
SELECT o.plant, o.line, l.category, o.month,
       SUM(o.planned_qty) AS planned_units, SUM(o.actual_qty) AS units,
       round(SUM(o.actual_material_cost), 0)                       AS actual_material,
       round(SUM(o.actual_conversion_cost), 0)                     AS actual_conversion,
       round(SUM(o.std_material), 0)                               AS std_material,
       round(SUM(o.std_conversion), 0)                             AS std_conversion,
       round(SUM(o.actual_material_cost - o.std_material), 0)      AS material_variance,
       round(SUM(o.actual_conversion_cost - o.std_conversion), 0)  AS conversion_variance,
       round(SUM(o.actual_material_cost + o.actual_conversion_cost) / NULLIF(SUM(o.actual_qty), 0), 1) AS actual_cost_per_unit,
       round(SUM(o.std_material + o.std_conversion) / NULLIF(SUM(o.actual_qty), 0), 1)               AS std_cost_per_unit,
       round(SUM(o.actual_conversion_cost) / NULLIF(SUM(o.actual_qty), 0), 1)                         AS conversion_per_unit,
       round(SUM(o.machine_hours), 1)                              AS machine_hours,
       c.available_hours, c.downtime_days,
       round(100 * SUM(o.machine_hours) / NULLIF(c.available_hours, 0), 1) AS utilisation_pct
FROM o
JOIN ref.lines l USING (line)
JOIN pp.plant_capacity c ON c.line = o.line AND c.month = o.month
GROUP BY o.plant, o.line, l.category, o.month, c.available_hours, c.downtime_days;

-- Returns by product, plant and the month the goods were invoiced (not the month the credit note was raised)
CREATE OR REPLACE VIEW rpt.return_rates AS
SELECT s.material, m.description, s.plant, s.invoice_month,
       SUM(s.quantity) FILTER (WHERE s.billing_type = 'F2')   AS units_invoiced,
       -SUM(s.quantity) FILTER (WHERE s.billing_type = 'G2')  AS units_returned,
       round(-SUM(s.quantity) FILTER (WHERE s.billing_type = 'G2')::NUMERIC
             / NULLIF(SUM(s.quantity) FILTER (WHERE s.billing_type = 'F2'), 0), 4) AS return_rate,
       -round(SUM(s.net_value) FILTER (WHERE s.billing_type = 'G2'), 0)            AS value_returned
FROM rpt.sales_lines s JOIN ref.materials m USING (material)
GROUP BY s.material, m.description, s.plant, s.invoice_month;
