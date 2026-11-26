-- =====================================================================
-- 08  Views shaped for Power BI
-- =====================================================================

-- Margin bridge in long format (one row per effect) for a waterfall chart
CREATE OR REPLACE VIEW rpt.margin_bridge_long AS
SELECT month, scope, category, e.effect, e.effect_order, e.value
FROM rpt.margin_bridge b
CROSS JOIN LATERAL (VALUES ('Volume', 1, b.volume), ('Mix', 2, b.mix), ('Price', 3, b.price),
                           ('Cost', 4, b.cost), ('Returns', 5, b.returns)) AS e(effect, effect_order, value);
