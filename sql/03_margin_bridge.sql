-- =====================================================================
-- 03  Margin bridge: why gross margin changed from one month to the next
--
-- For each month, category and scope (all regions, or one region), the change in gross margin is split into:
--   volume   more or fewer units, at last month's average margin per unit
--   mix      a different blend of products, at last month's margin per unit of each product
--   price    change in net price per unit (list price changes and discounts), at this month's units
--   cost     change in standard cost per unit (commodity prices), at this month's units
--   returns  change in the margin reversed by credit notes
-- The five add up exactly to the change. Products sold in only one of the two months are counted in mix.
-- =====================================================================

CREATE OR REPLACE VIEW rpt.bridge_base AS
SELECT month, 'All' AS scope, category, material,
       SUM(quantity) AS units, SUM(net_value) AS net, SUM(cost_at_standard) AS cost
FROM rpt.sales_lines WHERE billing_type = 'F2' GROUP BY month, category, material
UNION ALL
SELECT month, region, category, material, SUM(quantity), SUM(net_value), SUM(cost_at_standard)
FROM rpt.sales_lines WHERE billing_type = 'F2' GROUP BY month, region, category, material;

CREATE OR REPLACE VIEW rpt.returns_margin AS
SELECT month, 'All' AS scope, category, SUM(gross_margin) AS returns_margin
FROM rpt.sales_lines WHERE billing_type = 'G2' GROUP BY month, category
UNION ALL
SELECT month, region, category, SUM(gross_margin)
FROM rpt.sales_lines WHERE billing_type = 'G2' GROUP BY month, region, category;

CREATE OR REPLACE VIEW rpt.margin_bridge AS
WITH months AS (
    SELECT DISTINCT month,
           to_char(to_date(month || '-01', 'YYYY-MM-DD') - INTERVAL '1 month', 'YYYY-MM') AS prev_month
    FROM rpt.sales_lines
),
pairs AS (       -- each product in the current and previous month, side by side
    SELECT m.month, COALESCE(c.scope, p.scope) AS scope, COALESCE(c.category, p.category) AS category,
           COALESCE(c.units, 0) AS u_c, COALESCE(p.units, 0) AS u_p,
           c.net / NULLIF(c.units, 0) AS np_c, p.net / NULLIF(p.units, 0) AS np_p,
           c.cost / NULLIF(c.units, 0) AS sc_c, p.cost / NULLIF(p.units, 0) AS sc_p,
           COALESCE(c.net - c.cost, 0) AS m_c_total, COALESCE(p.net - p.cost, 0) AS m_p_total,
           -- last month's margin per unit; for a product new this month, this month's
           COALESCE((p.net - p.cost) / NULLIF(p.units, 0), (c.net - c.cost) / NULLIF(c.units, 0)) AS m_ref
    FROM months m
    JOIN rpt.bridge_base c ON c.month = m.month
    FULL JOIN rpt.bridge_base p ON p.month = m.prev_month AND p.scope = c.scope AND p.material = c.material
    WHERE m.month > (SELECT MIN(month) FROM rpt.sales_lines)
),
tot AS (
    SELECT month, scope, category,
           SUM(u_c) AS units_c, SUM(u_p) AS units_p,
           SUM(m_c_total) AS margin_c, SUM(m_p_total) AS margin_p,
           SUM(u_c * m_ref) AS margin_at_ref,
           SUM(CASE WHEN u_c > 0 AND u_p > 0 THEN u_c * (np_c - np_p) ELSE 0 END)  AS price,
           SUM(CASE WHEN u_c > 0 AND u_p > 0 THEN -u_c * (sc_c - sc_p) ELSE 0 END) AS cost
    FROM pairs WHERE month IS NOT NULL GROUP BY month, scope, category
)
SELECT t.month, t.scope, t.category,
       round(t.margin_p + COALESCE(rp.returns_margin, 0), 0)                              AS margin_prev,
       round(t.margin_c + COALESCE(rc.returns_margin, 0), 0)                              AS margin_now,
       round((t.units_c - t.units_p) * t.margin_p / NULLIF(t.units_p, 0), 0)               AS volume,
       round(t.margin_at_ref - t.units_c * t.margin_p / NULLIF(t.units_p, 0), 0)           AS mix,
       round(t.price, 0)                                                                   AS price,
       round(t.cost, 0)                                                                    AS cost,
       round(COALESCE(rc.returns_margin, 0) - COALESCE(rp.returns_margin, 0), 0)           AS returns,
       round(t.margin_c + COALESCE(rc.returns_margin, 0) - t.margin_p - COALESCE(rp.returns_margin, 0), 0) AS change
FROM tot t
LEFT JOIN rpt.returns_margin rc ON rc.month = t.month AND rc.scope = t.scope AND rc.category = t.category
LEFT JOIN rpt.returns_margin rp ON rp.scope = t.scope AND rp.category = t.category
     AND rp.month = to_char(to_date(t.month || '-01', 'YYYY-MM-DD') - INTERVAL '1 month', 'YYYY-MM');

-- Discount above the channel policy: what it cost, by month, region and channel
CREATE OR REPLACE VIEW rpt.discount_leakage AS
SELECT s.month, s.region, s.channel, p.max_discount_pct,
       round(SUM(s.discount_value) / NULLIF(SUM(s.gross_value), 0) * 100, 1) AS avg_discount_pct,
       COUNT(*) FILTER (WHERE s.discount_pct > p.max_discount_pct)        AS lines_above_policy,
       round(SUM(s.gross_value * GREATEST(s.discount_pct - p.max_discount_pct, 0) / 100), 0) AS leakage
FROM rpt.sales_lines s JOIN ref.discount_policy p USING (channel)
WHERE s.billing_type = 'F2'
GROUP BY s.month, s.region, s.channel, p.max_discount_pct;
