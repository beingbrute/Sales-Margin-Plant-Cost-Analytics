-- =====================================================================
-- 09  Field notes: themes tagged by a local language model (src/tag_field_notes.py)
-- The table is filled by src/load_data.py from data/derived/field_note_themes_llm.csv when that file exists.
-- =====================================================================
CREATE TABLE inp.field_note_themes (note_id TEXT PRIMARY KEY REFERENCES inp.field_notes, theme TEXT NOT NULL, model TEXT);

-- Notes per theme by region and month, with each theme's share of the region's notes that month
CREATE OR REPLACE VIEW rpt.field_note_themes AS
SELECT to_char(n.visit_date, 'YYYY-MM') AS month, n.region, t.theme, COUNT(*) AS notes,
       round(COUNT(*)::NUMERIC / SUM(COUNT(*)) OVER (PARTITION BY to_char(n.visit_date, 'YYYY-MM'), n.region), 3) AS share
FROM inp.field_notes n JOIN inp.field_note_themes t USING (note_id)
GROUP BY 1, 2, 3;

-- West: share of field notes about competitor pricing vs share of premium fans in fan units, by month
CREATE OR REPLACE VIEW rpt.west_competitor_signal AS
SELECT m.month,
       COALESCE((SELECT share FROM rpt.field_note_themes f
                 WHERE f.month = m.month AND f.region = 'West' AND f.theme = 'Competitor pricing'), 0) AS competitor_note_share,
       (SELECT unit_share FROM rpt.segment_mix s
        WHERE s.month = m.month AND s.region = 'West' AND s.category = 'Fans' AND s.segment = 'Premium') AS premium_fan_share
FROM (SELECT DISTINCT month FROM rpt.sales_lines) m;
