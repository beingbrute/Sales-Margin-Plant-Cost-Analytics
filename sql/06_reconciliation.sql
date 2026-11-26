-- =====================================================================
-- 06  Reconciliation: billing register vs revenue booked in the ledger
-- A difference in one month that reverses in the next points to a cut-off (posted in the wrong period).
-- =====================================================================
CREATE OR REPLACE VIEW rpt.revenue_reconciliation AS
WITH b AS (SELECT month, category, SUM(net_value) AS billing FROM rpt.sales_lines GROUP BY 1, 2)
SELECT COALESCE(b.month, g.fiscal_month) AS month, COALESCE(b.category, g.category) AS category,
       round(COALESCE(b.billing, 0), 2) AS billing_net_sales, round(COALESCE(g.revenue, 0), 2) AS ledger_revenue,
       round(COALESCE(g.revenue, 0) - COALESCE(b.billing, 0), 2) AS difference
FROM b FULL JOIN fi.gl_revenue g ON g.fiscal_month = b.month AND g.category = b.category;

CREATE OR REPLACE VIEW rpt.reconciliation_summary AS
SELECT month, SUM(billing_net_sales) AS billing_net_sales, SUM(ledger_revenue) AS ledger_revenue,
       SUM(difference) AS difference,
       CASE WHEN abs(SUM(difference)) < 1 THEN 'Matched' ELSE 'Difference' END AS status
FROM rpt.revenue_reconciliation GROUP BY month;

-- Invoices dated in the last days of a month: candidates when the ledger shows that month short
CREATE OR REPLACE VIEW rpt.month_end_invoices AS
SELECT month, billing_date, COUNT(DISTINCT billing_doc) AS invoices, round(SUM(net_value), 2) AS net_value
FROM rpt.sales_lines
WHERE billing_type = 'F2' AND billing_date >= (date_trunc('month', billing_date) + INTERVAL '1 month - 4 days')::date
GROUP BY month, billing_date;

-- =====================================================================
-- Risk and opportunity register. Every value is calculated from the views above, so it updates with the data.
-- ₹ values are for the year unless the basis says otherwise. Owners are roles, not people.
-- =====================================================================
CREATE OR REPLACE VIEW rpt.risk_opportunity AS
WITH copper AS (   -- copper in wires sold per month, at the latest copper price
    SELECT AVG(kg) AS kg_per_month, (SELECT copper_per_kg FROM ref.commodity_prices ORDER BY month DESC LIMIT 1) AS price
    FROM (SELECT s.month, SUM(s.quantity * b.copper_kg) AS kg FROM rpt.sales_lines s
          JOIN ref.bill_of_materials b USING (material) WHERE s.category = 'Wires' AND s.billing_type = 'F2' GROUP BY 1) x
), west AS (       -- West premium fan share before and after August, and margin per unit by segment from August
    SELECT SUM(units) FILTER (WHERE month < '2025-08' AND segment = 'Premium')::NUMERIC
             / SUM(units) FILTER (WHERE month < '2025-08') AS share_before,
           SUM(units) FILTER (WHERE month >= '2025-08' AND segment = 'Premium') AS prem_after,
           SUM(units) FILTER (WHERE month >= '2025-08') AS units_after
    FROM rpt.segment_mix WHERE region = 'West' AND category = 'Fans'
), wm AS (
    SELECT SUM(net_value - cost_at_standard) FILTER (WHERE segment = 'Premium') / SUM(quantity) FILTER (WHERE segment = 'Premium') AS prem,
           SUM(net_value - cost_at_standard) FILTER (WHERE segment <> 'Premium') / SUM(quantity) FILTER (WHERE segment <> 'Premium') AS other
    FROM rpt.sales_lines WHERE region = 'West' AND category = 'Fans' AND billing_type = 'F2' AND month >= '2025-08'
)
SELECT * FROM (VALUES
 ('R1', 'Risk', 'P1 Margin recovery', 'Copper price exposure in wires',
  (SELECT round(kg_per_month * price * 0.10 * 12, 0) FROM copper),
  'Margin lost in a year if copper rises 10% and wire prices do not move (wires only)',
  'Plant controller / Pricing', 'Agree a price-review trigger when copper moves more than 5%'),
 ('R2', 'Risk', 'P2 Plant and supply chain footprint', 'Baddi STB-L1 breakdown (single line for half the stabiliser range)',
  (SELECT conversion_variance FROM rpt.plant_cost WHERE line = 'STB-L1' AND month = '2025-11'),
  'Conversion cost above standard in November 2025',
  'Baddi plant head', 'Preventive maintenance plan; move urgent orders to STB-L2'),
 ('R3', 'Risk', 'P2 Plant and supply chain footprint', 'North water heater supply during winter',
  (SELECT SUM(margin_lost) FROM rpt.short_shipments WHERE region = 'North' AND category = 'Water heaters')
   + (SELECT SUM(extra_freight) FROM rpt.extra_freight WHERE to_warehouse = 'WN'),
  'Margin on unshipped orders plus extra freight from Hosur, Oct 2025 – Jan 2026',
  'Supply chain head', 'Build North stock before winter or add water heater capacity at Haridwar'),
 ('R4', 'Risk', 'P3 Channel profitability', 'Water heater WH006 quality (Hosur)',
  (SELECT SUM(value_returned) FROM rpt.return_rates WHERE material = 'WH006' AND plant = 'HSR'
     AND invoice_month IN ('2026-01', '2026-02')),
  'Sales value returned on January–February invoices',
  'Hosur quality head', 'Root-cause the January batch; hold stock until cleared'),
 ('R5', 'Risk', 'P3 Channel profitability', 'Competitor BLDC fans in the West',
  (SELECT round((share_before * units_after - prem_after) * (prem - other), 0) FROM west, wm),
  'Margin lost Aug–Mar because the West sold fewer premium fans than its Apr–Jul share',
  'West sales head', 'Price and feature review of the premium BLDC range'),
 ('O1', 'Opportunity', 'P1 Margin recovery', 'East distributor discounts above policy',
  (SELECT SUM(leakage) FROM rpt.discount_leakage WHERE region = 'East'),
  'Discount given above the 12% policy, Oct–Dec 2025',
  'East sales head / Finance', 'Approval for any discount above policy; recover where contracts allow'),
 ('O2', 'Opportunity', 'P1 Margin recovery', 'Faster copper pass-through',
  (SELECT -SUM(cost) FROM rpt.margin_bridge WHERE scope = 'All' AND category = 'Wires' AND month BETWEEN '2025-07' AND '2025-09'),
  'Wire margin lost to copper cost before the October price increase',
  'Pricing', 'Same trigger as R1; reprice within a month, not a quarter'),
 ('O3', 'Opportunity', 'P3 Channel profitability', 'E-commerce freight',
  (SELECT round(SUM(net_sales) * 0.01, 0) FROM rpt.sales_monthly WHERE channel = 'E-commerce'),
  'Contribution gained for each 1 point cut in e-commerce freight (now 5.5% of sales)',
  'E-commerce head / Logistics', 'Renegotiate last-mile rates; regional fulfilment for bulky items'),
 ('O4', 'Opportunity', 'Reporting', 'Revenue cut-off control',
  (SELECT MAX(abs(difference)) FROM rpt.reconciliation_summary),
  'Revenue booked in the wrong month (December invoices in January); not a loss',
  'Finance controller', 'Month-end check of billing vs ledger before close')
) AS r(id, type, project, item, value_inr, basis, owner, action);
