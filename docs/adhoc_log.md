# Ad hoc analysis log

Ten questions of the kind a COO's office asks during the month (written as examples: Orvane is fictional and nobody asked them), each answered with one query against the `orvane` database. Written by `src/build_adhoc_log.py`; the answers are generated from the query results, so re-running the script after a data change updates them. Run time is the query's time on a laptop (PostgreSQL 17), not the time to write it.

| # | Asked by | Question | Query time |
|---|---|---|---|
| 1 | COO | [Why did wire margin fall in July and August?](#q1) | 2,040 ms |
| 2 | East sales head | [Which customers drive the East discounts above policy?](#q2) | 55 ms |
| 3 | COO | [How dependent are we on our biggest customers?](#q3) | 152 ms |
| 4 | COO | [Which channel keeps the least margin after freight?](#q4) | 108 ms |
| 5 | West sales head | [Which fan products lost the most in the West since August?](#q5) | 111 ms |
| 6 | COO | [Which plant line ran furthest over standard cost, and why?](#q6) | 19 ms |
| 7 | Finance controller | [What share of each month's billing lands in the last four days?](#q7) | 170 ms |
| 8 | COO | [How accurate was the sales team's unit forecast?](#q8) | 80 ms |
| 9 | COO | [Which assumptions from the functions did not hold?](#q9) | 7 ms |
| 10 | COO | [How much margin did customer returns cost, and where?](#q10) | 198 ms |

## Q1. Why did wire margin fall in July and August? <a id="q1"></a>
*Asked by: COO · query time 2,040 ms*

**Answer.** Cost, not volume or price: the cost effect was ₹278.9 lakh in July and ₹283.4 lakh in August, as copper went from ₹790 to ₹921 per kg. The October price increase brought ₹781.1 lakh back in one month.

```sql
SELECT b.month, round(b.change / 1e5, 1) AS change_lakh, round(b.cost / 1e5, 1) AS cost_effect_lakh,
       round(b.price / 1e5, 1) AS price_effect_lakh, w.copper_per_kg
FROM rpt.margin_bridge b JOIN rpt.wire_cost_monthly w USING (month)
WHERE b.scope = 'All' AND b.category = 'Wires' AND b.month BETWEEN '2025-06' AND '2025-10'
ORDER BY b.month
```

| month | change_lakh | cost_effect_lakh | price_effect_lakh | copper_per_kg |
|---|---|---|---|---|
| 2025-06 | -81.2 | -27.4 | 6.1 | 790.0 |
| 2025-07 | -298.2 | -278.9 | -5.0 | 845.0 |
| 2025-08 | -270.4 | -283.4 | 2.0 | 900.0 |
| 2025-09 | -42.4 | -120.6 | 3.5 | 921.0 |
| 2025-10 | 861.0 | 35.6 | 781.1 | 915.0 |

## Q2. Which customers drive the East discounts above policy? <a id="q2"></a>
*Asked by: East sales head · query time 55 ms*

**Answer.** 39 East customers got discounts above policy, worth ₹519.1 lakh in total. The top 20 account for 56.6% of it, so a sign-off for any discount above policy on those 20 accounts would cover more than half of it.

```sql
WITH leak AS (
    SELECT s.customer, c.customer_name, c.city,
           SUM((s.discount_pct - p.max_discount_pct) / 100 * s.gross_value) AS above_policy
    FROM rpt.sales_lines s
    JOIN ref.customers c USING (customer)
    JOIN ref.discount_policy p ON p.channel = s.channel
    WHERE s.region = 'East' AND s.billing_type = 'F2' AND s.discount_pct > p.max_discount_pct
    GROUP BY 1, 2, 3)
SELECT customer, customer_name, city, round(above_policy / 1e5, 1) AS above_policy_lakh,
       round(100 * above_policy / SUM(above_policy) OVER (), 1) AS share_pct,
       round(100 * SUM(above_policy) OVER (ORDER BY above_policy DESC) / SUM(above_policy) OVER (), 1) AS cumulative_pct,
       COUNT(*) OVER () AS customers
FROM leak ORDER BY above_policy DESC
```

| customer | customer_name | city | above_policy_lakh | share_pct | cumulative_pct | customers |
|---|---|---|---|---|---|---|
| C00006 | DIS customer 006 | Kolkata | 16.3 | 3.1 | 3.1 | 39 |
| C00197 | DIS customer 197 | Ranchi | 16.3 | 3.1 | 6.3 | 39 |
| C00171 | DIS customer 171 | Kolkata | 16.0 | 3.1 | 9.4 | 39 |
| C00136 | DIS customer 136 | Patna | 16.0 | 3.1 | 12.4 | 39 |
| C00055 | DIS customer 055 | Kolkata | 15.6 | 3.0 | 15.5 | 39 |
| C00033 | DIS customer 033 | Ranchi | 15.5 | 3.0 | 18.5 | 39 |
| C00216 | DIS customer 216 | Patna | 15.4 | 3.0 | 21.4 | 39 |
| C00121 | DIS customer 121 | Kolkata | 15.1 | 2.9 | 24.3 | 39 |
| C00177 | DIS customer 177 | Ranchi | 15.0 | 2.9 | 27.2 | 39 |
| C00125 | DIS customer 125 | Guwahati | 15.0 | 2.9 | 30.1 | 39 |
| C00081 | DIS customer 081 | Ranchi | 14.8 | 2.9 | 33.0 | 39 |
| C00124 | DIS customer 124 | Patna | 14.6 | 2.8 | 35.8 | 39 |

## Q3. How dependent are we on our biggest customers? <a id="q3"></a>
*Asked by: COO · query time 152 ms*

**Answer.** Not heavily: the top 10 of 400 customers are 3.8% of net sales and the top 20 are 7.5%. Losing any single customer would not move the year by much.

```sql
WITH c AS (
    SELECT customer, SUM(net_value) AS net FROM rpt.sales_lines GROUP BY 1)
SELECT n_customers, round(100 * top_net / total, 1) AS share_of_net_sales_pct
FROM (SELECT SUM(net) AS total FROM c) t,
     LATERAL (VALUES (10), (20), (50), (100)) v(n_customers),
     LATERAL (SELECT SUM(net) AS top_net FROM (SELECT net FROM c ORDER BY net DESC LIMIT v.n_customers) x) y
ORDER BY n_customers
```

| n_customers | share_of_net_sales_pct |
|---|---|
| 10 | 3.8 |
| 20 | 7.5 |
| 50 | 18.3 |
| 100 | 35.7 |

## Q4. Which channel keeps the least margin after freight? <a id="q4"></a>
*Asked by: COO · query time 108 ms*

**Answer.** E-commerce: 28.0% gross margin, but freight takes 5.5 points, leaving 22.5%, the lowest of the four channels. Every point of freight saved there is worth ₹0.64 crore a year at this year's sales.

```sql
SELECT channel, round(net_sales / 1e7, 1) AS net_sales_cr, gross_margin_pct, freight_pct, contribution_pct
FROM rpt.margin_by_channel ORDER BY contribution_pct
```

| channel | net_sales_cr | gross_margin_pct | freight_pct | contribution_pct |
|---|---|---|---|---|
| E-commerce | 64.3 | 28.0 | 5.5 | 22.5 |
| Institutional | 422.6 | 24.0 | 1.0 | 23.0 |
| Distributor | 1919.4 | 25.2 | 1.2 | 24.0 |
| Modern retail | 184.3 | 31.2 | 1.6 | 29.6 |

## Q5. Which fan products lost the most in the West since August? <a id="q5"></a>
*Asked by: West sales head · query time 111 ms*

**Answer.** Fan sales fall everywhere after the summer, so each product's West change is compared with the other regions. The products that fell furthest beyond the seasonal drop are all Premium: BLDC Premium ceiling fan 1200mm (FN018) fell 70% in the West against 20% elsewhere. That fits the field notes: West notes about competitor BLDC fans rose from about 20% to 41–54% of notes in Aug–Sep.

```sql
WITH u AS (
    SELECT s.material, m.description, s.segment, (s.region = 'West') AS west,
           SUM(s.quantity) FILTER (WHERE s.month BETWEEN '2025-04' AND '2025-07') / 4.0 AS apr_jul,
           SUM(s.quantity) FILTER (WHERE s.month BETWEEN '2025-08' AND '2026-03') / 8.0 AS aug_mar
    FROM rpt.sales_lines s JOIN ref.materials m USING (material)
    WHERE s.category = 'Fans' AND s.billing_type = 'F2'
    GROUP BY 1, 2, 3, 4)
SELECT w.material, w.description, w.segment,
       round(100 * (w.aug_mar / w.apr_jul - 1), 1) AS west_change_pct,
       round(100 * (o.aug_mar / o.apr_jul - 1), 1) AS other_regions_change_pct,
       round(100 * (w.aug_mar / w.apr_jul - o.aug_mar / o.apr_jul), 1) AS west_gap_pts
FROM u w JOIN u o ON o.material = w.material AND NOT o.west
WHERE w.west ORDER BY west_gap_pts LIMIT 6
```

| material | description | segment | west_change_pct | other_regions_change_pct | west_gap_pts |
|---|---|---|---|---|---|
| FN018 | BLDC Premium ceiling fan 1200mm | Premium | -70.0 | -19.5 | -50.4 |
| FN016 | Premium ceiling fan 900mm | Premium | -74.1 | -25.4 | -48.6 |
| FN017 | BLDC Premium ceiling fan 1200mm | Premium | -66.4 | -29.6 | -36.8 |
| FN015 | Premium ceiling fan 1200mm | Premium | -58.1 | -26.7 | -31.4 |
| FN013 | Mid ceiling fan 900mm | Mid | -40.2 | -29.8 | -10.4 |
| FN009 | Mid ceiling fan 1200mm | Mid | -38.0 | -28.5 | -9.6 |

## Q6. Which plant line ran furthest over standard cost, and why? <a id="q6"></a>
*Asked by: COO · query time 19 ms*

**Answer.** BDI STB-L1 in 2025-11: ₹4,143 per unit against a standard of ₹2,107 (97% over), because 21 days of downtime left it at 9.8% utilisation. The next worst are HSR WH-L2 in the summer months, running at 13–18% utilisation: idle capacity, not breakdowns.

```sql
SELECT plant, line, category, month, units, actual_cost_per_unit, std_cost_per_unit,
       round(100 * (actual_cost_per_unit / std_cost_per_unit - 1), 1) AS over_std_pct, utilisation_pct, downtime_days
FROM rpt.plant_cost ORDER BY actual_cost_per_unit / std_cost_per_unit DESC LIMIT 6
```

| plant | line | category | month | units | actual_cost_per_unit | std_cost_per_unit | over_std_pct | utilisation_pct | downtime_days |
|---|---|---|---|---|---|---|---|---|---|
| BDI | STB-L1 | Stabilisers | 2025-11 | 6,744 | 4143.1 | 2106.7 | 96.7 | 9.8 | 21 |
| HSR | WH-L2 | Water heaters | 2025-05 | 17,628 | 7749.3 | 5524.0 | 40.3 | 13.0 | 0 |
| HSR | WH-L2 | Water heaters | 2025-06 | 20,299 | 7532.2 | 5772.9 | 30.5 | 15.0 | 0 |
| HSR | WH-L2 | Water heaters | 2025-04 | 23,220 | 7034.6 | 5604.8 | 25.5 | 17.2 | 0 |
| HSR | WH-L2 | Water heaters | 2025-07 | 24,135 | 6990.7 | 5660.9 | 23.5 | 17.9 | 0 |
| HSR | WH-L2 | Water heaters | 2025-08 | 26,256 | 6916.9 | 5797.7 | 19.3 | 19.5 | 0 |

## Q7. What share of each month's billing lands in the last four days? <a id="q7"></a>
*Asked by: Finance controller · query time 170 ms*

**Answer.** Between 11.4% and 14.7% every month. December was 14.1%, the highest in value (₹37.83 crore) but not unusual as a share. So the December cut-off error could not be spotted from billing timing; it showed only when billing was reconciled to the ledger.

```sql
WITH m AS (SELECT month, SUM(net_value) AS net FROM rpt.sales_lines WHERE billing_type = 'F2' GROUP BY 1),
e AS (SELECT month, SUM(net_value) AS net_last4, SUM(invoices) AS invoices_last4 FROM rpt.month_end_invoices GROUP BY 1)
SELECT month, invoices_last4, round(net_last4 / 1e7, 2) AS last4_cr, round(100 * net_last4 / net, 1) AS share_pct
FROM m JOIN e USING (month) ORDER BY month
```

| month | invoices_last4 | last4_cr | share_pct |
|---|---|---|---|
| 2025-04 | 281.0 | 26.65 | 13.3 |
| 2025-05 | 280.0 | 27.71 | 13.7 |
| 2025-06 | 251.0 | 26.47 | 14.7 |
| 2025-07 | 203.0 | 20.28 | 12.2 |
| 2025-08 | 205.0 | 22.26 | 13.3 |
| 2025-09 | 201.0 | 23.31 | 12.4 |
| 2025-10 | 211.0 | 25.91 | 11.4 |
| 2025-11 | 247.0 | 29.56 | 11.6 |
| 2025-12 | 262.0 | 37.83 | 14.1 |
| 2026-01 | 249.0 | 31.3 | 11.9 |
| 2026-02 | 280.0 | 31.53 | 12.6 |
| 2026-03 | 273.0 | 27.88 | 11.6 |

## Q8. How accurate was the sales team's unit forecast? <a id="q8"></a>
*Asked by: COO · query time 80 ms*

**Answer.** Average monthly error (MAPE) was 4.7–6.4% by category, and over the year the forecast was -1.3% to +2.4% against actual units. Usable for planning, but individual months were off by up to 12%, so plant plans need a buffer.

```sql
WITH f AS (
    SELECT split_part(key, '|', 1) AS month, split_part(key, '|', 2) AS category, value AS forecast
    FROM inp.function_inputs WHERE input = 'Unit sales forecast'),
a AS (
    SELECT month, category, SUM(quantity) AS actual FROM rpt.sales_lines WHERE billing_type = 'F2' GROUP BY 1, 2)
SELECT category, round(AVG(ABS(forecast - actual) / actual) * 100, 1) AS mape_pct,
       round(100 * (SUM(forecast) / SUM(actual) - 1), 1) AS bias_pct,
       round(100 * MAX(ABS(forecast - actual) / actual), 1) AS worst_month_error_pct
FROM f JOIN a USING (month, category) GROUP BY 1 ORDER BY 2 DESC
```

| category | mape_pct | bias_pct | worst_month_error_pct |
|---|---|---|---|
| Fans | 6.4 | 2.4 | 11.4 |
| Stabilisers | 5.4 | 2.4 | 10.8 |
| Water heaters | 5.3 | 0.1 | 11.5 |
| Wires | 4.7 | -1.3 | 10.0 |

## Q9. Which assumptions from the functions did not hold? <a id="q9"></a>
*Asked by: COO · query time 7 ms*

**Answer.** Copper: the plan assumed ₹800 per kg for Jul–Mar, the actual average was ₹899 (12% higher). Baddi planned 26 working days on STB-L1 in November and got 5. The wire price increase went through as planned (12%).

```sql
SELECT 'Copper price, Jul-Mar (INR/kg)' AS input, 'Plant controller' AS provided_by,
       (SELECT value FROM inp.function_inputs WHERE input = 'Copper price assumption Jul-Mar') AS assumed,
       (SELECT round(AVG(copper_per_kg), 1) FROM ref.commodity_prices WHERE month >= '2025-07') AS actual
UNION ALL
SELECT 'Baddi STB-L1 working days, Nov 2025', 'BDI plant head',
       (SELECT value FROM inp.function_inputs WHERE input = 'Planned working days' AND key = '2025-11|STB-L1'),
       (SELECT 26 - downtime_days FROM rpt.plant_cost WHERE line = 'STB-L1' AND month = '2025-11')
UNION ALL
SELECT 'Wire price increase (%)', 'Plant controller',
       (SELECT value FROM inp.function_inputs WHERE input = 'Planned wire price increase'),
       (SELECT round(100 * (AVG(p.list_price) FILTER (WHERE valid_from >= '2025-10-01') /
                            AVG(p.list_price) FILTER (WHERE valid_from < '2025-10-01') - 1), 1)
        FROM ref.price_list p JOIN ref.materials m USING (material) WHERE m.category = 'Wires')
```

| input | provided_by | assumed | actual |
|---|---|---|---|
| Copper price, Jul-Mar (INR/kg) | Plant controller | 800.0 | 899.0 |
| Baddi STB-L1 working days, Nov 2025 | BDI plant head | 26.0 | 5.0 |
| Wire price increase (%) | Plant controller | 12.0 | 12.0 |

## Q10. How much margin did customer returns cost, and where? <a id="q10"></a>
*Asked by: COO · query time 198 ms*

**Answer.** ₹523.3 lakh of gross margin for the year, the most in Water heaters (₹216.9 lakh). One product stands out: WH006 from Hosur had 6.9% of January and 5.3% of February invoices returned, against 0.8% for a normal product-month.

```sql
WITH r AS (
    SELECT material, plant, invoice_month, return_rate,
           (material = 'WH006' AND plant = 'HSR' AND invoice_month IN ('2026-01', '2026-02')) AS flagged
    FROM rpt.return_rates)
SELECT m.category, round(-SUM(m.returns_margin) / 1e5, 1) AS margin_lost_lakh,
       (SELECT round(100 * AVG(return_rate), 2) FROM r WHERE NOT flagged) AS normal_return_rate_pct,
       (SELECT round(100 * return_rate, 2) FROM r WHERE material = 'WH006' AND plant = 'HSR' AND invoice_month = '2026-01') AS wh006_jan_pct,
       (SELECT round(100 * return_rate, 2) FROM r WHERE material = 'WH006' AND plant = 'HSR' AND invoice_month = '2026-02') AS wh006_feb_pct
FROM rpt.returns_margin m WHERE m.scope = 'All' GROUP BY 1 ORDER BY 2 DESC
```

| category | margin_lost_lakh | normal_return_rate_pct | wh006_jan_pct | wh006_feb_pct |
|---|---|---|---|---|
| Water heaters | 216.9 | 0.79 | 6.91 | 5.28 |
| Fans | 118.1 | 0.79 | 6.91 | 5.28 |
| Wires | 114.6 | 0.79 | 6.91 | 5.28 |
| Stabilisers | 73.7 | 0.79 | 6.91 | 5.28 |
