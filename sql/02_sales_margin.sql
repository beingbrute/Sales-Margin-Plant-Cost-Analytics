-- =====================================================================
-- 02  Sales and margin
-- Metric definitions: docs/design.md, section 3. Every report reads these views.
-- =====================================================================

-- One row per billing line with its product, customer and margin.
-- Credit notes (G2) carry negative quantity and value, so sums give net figures.
-- invoice_month: for a credit note, the month of the invoice it reverses (used for return rates).
CREATE MATERIALIZED VIEW rpt.sales_lines AS
SELECT b.billing_type, b.billing_doc, b.item, b.billing_date, to_char(b.billing_date, 'YYYY-MM') AS month,
       to_char(COALESCE(inv.billing_date, b.billing_date), 'YYYY-MM')                AS invoice_month,
       b.customer, c.channel, c.region, b.material, m.category, m.segment, b.plant,
       b.ordered_qty, b.quantity, b.list_price, b.discount_pct,
       b.gross_value, b.gross_value - b.net_value                                    AS discount_value,
       b.net_value, b.cost_at_standard,
       b.net_value - b.cost_at_standard                                              AS gross_margin,
       b.freight,
       b.net_value - b.cost_at_standard - b.freight                                  AS contribution
FROM sd.billing b
JOIN ref.customers c USING (customer)
JOIN ref.materials m USING (material)
LEFT JOIN (SELECT DISTINCT billing_doc, billing_date FROM sd.billing WHERE billing_type = 'F2') inv
       ON inv.billing_doc = b.reference_doc
WITH NO DATA;

-- Monthly sales and margin by category, region and channel
CREATE OR REPLACE VIEW rpt.sales_monthly AS
SELECT month, category, region, channel,
       SUM(quantity) FILTER (WHERE billing_type = 'F2')       AS units_invoiced,
       -SUM(quantity) FILTER (WHERE billing_type = 'G2')      AS units_returned,
       SUM(gross_value)                                        AS gross_sales,
       SUM(discount_value)                                     AS discount,
       SUM(net_value)                                          AS net_sales,
       SUM(cost_at_standard)                                   AS cogs,
       SUM(gross_margin)                                       AS gross_margin,
       SUM(freight)                                            AS freight,
       SUM(contribution)                                       AS contribution
FROM rpt.sales_lines
GROUP BY month, category, region, channel;

-- Margin % by category and month (ratios of totals)
CREATE OR REPLACE VIEW rpt.margin_by_category AS
SELECT month, category, SUM(net_sales) AS net_sales, SUM(gross_margin) AS gross_margin, SUM(contribution) AS contribution,
       round(100 * SUM(gross_margin) / NULLIF(SUM(net_sales), 0), 1) AS gross_margin_pct,
       round(100 * SUM(contribution) / NULLIF(SUM(net_sales), 0), 1) AS contribution_pct
FROM rpt.sales_monthly GROUP BY month, category;

-- Margin % by channel for the year: gross vs contribution (freight is the difference)
CREATE OR REPLACE VIEW rpt.margin_by_channel AS
SELECT channel, SUM(units_invoiced) AS units, SUM(net_sales) AS net_sales,
       round(100 * SUM(gross_margin) / SUM(net_sales), 1) AS gross_margin_pct,
       round(100 * SUM(freight) / SUM(net_sales), 1)      AS freight_pct,
       round(100 * SUM(contribution) / SUM(net_sales), 1) AS contribution_pct
FROM rpt.sales_monthly GROUP BY channel;

-- Units sold per month by channel (e-commerce growth)
CREATE OR REPLACE VIEW rpt.channel_trend AS
SELECT month, channel, SUM(units_invoiced) AS units, round(SUM(net_sales) / 1e7, 2) AS net_sales_cr
FROM rpt.sales_monthly GROUP BY month, channel;

-- Share of each segment in a category's units, by region and month (mix)
CREATE OR REPLACE VIEW rpt.segment_mix AS
SELECT month, region, category, segment, SUM(quantity) AS units,
       round(SUM(quantity)::NUMERIC / SUM(SUM(quantity)) OVER (PARTITION BY month, region, category), 3) AS unit_share
FROM rpt.sales_lines WHERE billing_type = 'F2'
GROUP BY month, region, category, segment;
