# Data dictionary

Every table and view in the `orvane` database. Written by `src/build_data_dictionary.py` from the database itself, so names and types match what is loaded. Metric definitions: `docs/design.md`, section 3. All data is synthetic.

## `ref`: Master data (SAP: plants, materials, condition records, customers)

### `ref.bill_of_materials` (table · 52 rows)
Copper, steel and plastic per unit of each product, used to cost raw material.

| Column | Type | Meaning |
|---|---|---|
| `material` | text | Product code (ref.materials) |
| `copper_kg` | numeric(8,3) |  |
| `steel_kg` | numeric(8,3) |  |
| `plastic_kg` | numeric(8,3) |  |

### `ref.commodity_prices` (table · 12 rows)
Copper, steel and plastic price per kg by month.

| Column | Type | Meaning |
|---|---|---|
| `month` | text | Calendar month, text YYYY-MM |
| `copper_per_kg` | numeric(10,2) |  |
| `steel_per_kg` | numeric(10,2) |  |
| `plastic_per_kg` | numeric(10,2) |  |

### `ref.customers` (table · 400 rows)
One row per customer (KNA1/KNVV): channel, region, city.

| Column | Type | Meaning |
|---|---|---|
| `customer` | text | Customer code (ref.customers) |
| `customer_name` | text |  |
| `channel` | text | Distributor, Modern retail, E-commerce or Institutional |
| `region` | text | North, South, East or West |
| `city` | text |  |

### `ref.discount_policy` (table · 4 rows)
Maximum discount allowed per channel (K007).

| Column | Type | Meaning |
|---|---|---|
| `channel` | text | Distributor, Modern retail, E-commerce or Institutional |
| `max_discount_pct` | numeric(5,2) |  |

### `ref.lines` (table · 8 rows)
One row per production line, with the category it makes and its fixed cost per month.

| Column | Type | Meaning |
|---|---|---|
| `plant` | text | HDW Haridwar, BDI Baddi, HSR Hosur |
| `line` | text | Production line (ref.lines) |
| `category` | text | Fans, Wires, Water heaters or Stabilisers |
| `fixed_cost_month` | numeric(14,2) |  |

### `ref.materials` (table · 52 rows)
One row per product (MARA/MARC): category, segment, list price, producing plant and line.

| Column | Type | Meaning |
|---|---|---|
| `material` | text | Product code (ref.materials) |
| `description` | text |  |
| `category` | text | Fans, Wires, Water heaters or Stabilisers |
| `segment` | text | Economy, Mid or Premium |
| `list_price` | numeric(12,2) |  |
| `conversion_std` | numeric(12,2) |  |
| `packing` | numeric(12,2) |  |
| `plant` | text | HDW Haridwar, BDI Baddi, HSR Hosur |
| `line` | text | Production line (ref.lines) |
| `machine_hours_per_unit` | numeric(8,4) |  |
| `weight_kg` | numeric(8,2) |  |

### `ref.plants` (table · 3 rows)
One row per plant (SAP T001W).

| Column | Type | Meaning |
|---|---|---|
| `plant` | text | HDW Haridwar, BDI Baddi, HSR Hosur |
| `plant_name` | text |  |
| `city` | text |  |
| `zone` | text |  |

### `ref.price_list` (table · 68 rows)
List price per product with the date it applies from (PR00). Wires have a new price from 1 October 2025.

| Column | Type | Meaning |
|---|---|---|
| `material` | text | Product code (ref.materials) |
| `valid_from` | date | Date the price or cost applies from |
| `list_price` | numeric(12,2) |  |

### `ref.standard_costs` (table · 624 rows)
Standard cost per unit by product and month (CK11 cost estimate); raw material follows commodity prices.

| Column | Type | Meaning |
|---|---|---|
| `material` | text | Product code (ref.materials) |
| `valid_from` | date | Date the price or cost applies from |
| `raw_material` | numeric(12,2) |  |
| `conversion` | numeric(12,2) |  |
| `packing` | numeric(12,2) |  |
| `standard_cost` | numeric(12,2) |  |

### `ref.warehouses` (table · 4 rows)
One row per regional warehouse; region links customers to warehouses.

| Column | Type | Meaning |
|---|---|---|
| `warehouse` | text | WN Gurugram, WS Bengaluru, WE Kolkata, WW Bhiwandi |
| `warehouse_name` | text |  |
| `city` | text |  |
| `region` | text | North, South, East or West |

## `sd`: Sales and distribution: billing documents

### `sd.billing` (table · 156,494 rows)
One row per billing line (VBRK/VBRP), after cleaning. F2 = invoice, G2 = credit note (negative quantity and value).

| Column | Type | Meaning |
|---|---|---|
| `billing_type` | text | F2 = invoice, G2 = credit note |
| `billing_doc` | bigint |  |
| `item` | integer |  |
| `billing_date` | date |  |
| `customer` | text | Customer code (ref.customers) |
| `material` | text | Product code (ref.materials) |
| `plant` | text | HDW Haridwar, BDI Baddi, HSR Hosur |
| `ordered_qty` | integer | Quantity the customer ordered; quantity is what was invoiced |
| `quantity` | integer |  |
| `list_price` | numeric(12,2) |  |
| `discount_pct` | numeric(5,2) | Discount given on the line, % of list price |
| `gross_value` | numeric(14,2) |  |
| `net_value` | numeric(14,2) | Value after discount; negative on credit notes |
| `cost_at_standard` | numeric(14,2) | Quantity × standard cost for the billing month |
| `freight` | numeric(12,2) |  |
| `reference_doc` | bigint | For a credit note: the invoice it reverses |
| `unit` | text |  |

## `pp`: Production planning: production orders and line capacity

### `pp.plant_capacity` (table · 96 rows)
One row per line and month: available machine hours, downtime days, fixed cost.

| Column | Type | Meaning |
|---|---|---|
| `plant` | text | HDW Haridwar, BDI Baddi, HSR Hosur |
| `line` | text | Production line (ref.lines) |
| `month` | text | Calendar month, text YYYY-MM |
| `available_hours` | numeric(8,1) |  |
| `downtime_days` | integer |  |
| `fixed_cost` | numeric(14,2) |  |

### `pp.production_orders` (table · 744 rows)
One row per production order (AFKO/AFPO): planned and actual quantity, actual cost, machine hours.

| Column | Type | Meaning |
|---|---|---|
| `production_order` | bigint |  |
| `plant` | text | HDW Haridwar, BDI Baddi, HSR Hosur |
| `line` | text | Production line (ref.lines) |
| `material` | text | Product code (ref.materials) |
| `month` | text | Calendar month, text YYYY-MM |
| `planned_qty` | integer |  |
| `actual_qty` | integer |  |
| `actual_material_cost` | numeric(14,2) |  |
| `machine_hours` | numeric(10,1) |  |
| `actual_conversion_cost` | numeric(14,2) |  |

## `mm`: Materials management: stock transfers and warehouse stock

### `mm.stock_transfers` (table · 5,068 rows)
One row per plant-to-warehouse shipment (STO), with freight cost.

| Column | Type | Meaning |
|---|---|---|
| `sto_no` | bigint |  |
| `from_plant` | text | HDW Haridwar, BDI Baddi, HSR Hosur |
| `to_warehouse` | text | WN Gurugram, WS Bengaluru, WE Kolkata, WW Bhiwandi |
| `material` | text | Product code (ref.materials) |
| `quantity` | integer |  |
| `dispatch_date` | date |  |
| `receipt_date` | date |  |
| `freight_cost` | numeric(12,2) |  |

### `mm.warehouse_stock` (table · 2,496 rows)
Closing stock per warehouse, product and month end (MB52).

| Column | Type | Meaning |
|---|---|---|
| `warehouse` | text | WN Gurugram, WS Bengaluru, WE Kolkata, WW Bhiwandi |
| `material` | text | Product code (ref.materials) |
| `month` | text | Calendar month, text YYYY-MM |
| `closing_qty` | integer |  |

## `fi`: Finance: general ledger revenue

### `fi.gl_revenue` (table · 48 rows)
Revenue booked in the ledger per month and category (FAGLFLEXT); used to reconcile billing.

| Column | Type | Meaning |
|---|---|---|
| `fiscal_month` | text |  |
| `category` | text | Fans, Wires, Water heaters or Stabilisers |
| `revenue` | numeric(16,2) |  |

## `inp`: Inputs from functions and the sales team

### `inp.field_note_themes` (table · 1,200 rows)
Theme of each field note, tagged by a local language model (src/tag_field_notes.py).

| Column | Type | Meaning |
|---|---|---|
| `note_id` | text |  |
| `theme` | text |  |
| `model` | text |  |

### `inp.field_notes` (table · 1,200 rows)
Sales team visit notes, one per visit.

| Column | Type | Meaning |
|---|---|---|
| `note_id` | text |  |
| `visit_date` | date |  |
| `region` | text | North, South, East or West |
| `channel` | text | Distributor, Modern retail, E-commerce or Institutional |
| `note` | text |  |

### `inp.function_inputs` (table · 159 rows)
Inputs register: what each function provided (sales forecast, planned working days, freight rates, cost assumptions). Template: templates/function_inputs_template.xlsx.

| Column | Type | Meaning |
|---|---|---|
| `function` | text |  |
| `provided_by` | text |  |
| `input` | text |  |
| `key` | text | Month|category, month|line or plant|warehouse, depending on the input |
| `value` | numeric(14,3) |  |
| `unit` | text |  |

## `etl`: Data preparation records

### `etl.cleaning_log` (table · 5 rows)
One row per cleaning rule: rows changed or removed and the net value removed.

| Column | Type | Meaning |
|---|---|---|
| `rule` | text |  |
| `dataset` | text |  |
| `action` | text |  |
| `rows` | integer |  |
| `net_value_removed` | numeric(16,2) |  |

## `rpt`: Reporting views: every metric is defined here once and read by Excel, Power BI and the scripts

### `rpt.bridge_base` (view)
Units, net sales and standard cost by month, scope (All or a region), category and product; input to the margin bridge.

| Column | Type | Meaning |
|---|---|---|
| `month` | text | Calendar month, text YYYY-MM |
| `scope` | text | All = whole company; otherwise a region |
| `category` | text | Fans, Wires, Water heaters or Stabilisers |
| `material` | text | Product code (ref.materials) |
| `units` | bigint |  |
| `net` | numeric |  |
| `cost` | numeric |  |

### `rpt.channel_trend` (view)
Units and net sales by month and channel.

| Column | Type | Meaning |
|---|---|---|
| `month` | text | Calendar month, text YYYY-MM |
| `channel` | text | Distributor, Modern retail, E-commerce or Institutional |
| `units` | numeric |  |
| `net_sales_cr` | numeric |  |

### `rpt.days_of_stock` (view)
Closing stock ÷ average daily sales by month, region and category.

| Column | Type | Meaning |
|---|---|---|
| `month` | text | Calendar month, text YYYY-MM |
| `region` | text | North, South, East or West |
| `category` | text | Fans, Wires, Water heaters or Stabilisers |
| `closing_qty` | bigint |  |
| `units_sold` | bigint |  |
| `days_of_stock` | numeric |  |

### `rpt.discount_leakage` (view)
Discount given above the channel policy, by month, region and channel.

| Column | Type | Meaning |
|---|---|---|
| `month` | text | Calendar month, text YYYY-MM |
| `region` | text | North, South, East or West |
| `channel` | text | Distributor, Modern retail, E-commerce or Institutional |
| `max_discount_pct` | numeric(5,2) |  |
| `avg_discount_pct` | numeric |  |
| `lines_above_policy` | bigint |  |
| `leakage` | numeric | Gross value × (discount % − policy maximum), where above policy |

### `rpt.extra_freight` (view)
Freight paid above the normal lane when a warehouse is supplied from another plant.

| Column | Type | Meaning |
|---|---|---|
| `month` | text | Calendar month, text YYYY-MM |
| `from_plant` | text | HDW Haridwar, BDI Baddi, HSR Hosur |
| `to_warehouse` | text | WN Gurugram, WS Bengaluru, WE Kolkata, WW Bhiwandi |
| `category` | text | Fans, Wires, Water heaters or Stabilisers |
| `units` | bigint |  |
| `freight_per_unit` | numeric |  |
| `normal_freight_per_unit` | numeric |  |
| `extra_freight` | numeric |  |

### `rpt.field_note_themes` (view)
Field notes per theme by month and region, with each theme's share of the region's notes.

| Column | Type | Meaning |
|---|---|---|
| `month` | text | Calendar month, text YYYY-MM |
| `region` | text | North, South, East or West |
| `theme` | text |  |
| `notes` | bigint |  |
| `share` | numeric | Share of the region's notes that month (0–1) |

### `rpt.fill_rate` (view)
Invoiced quantity ÷ ordered quantity by month, region and category.

| Column | Type | Meaning |
|---|---|---|
| `month` | text | Calendar month, text YYYY-MM |
| `region` | text | North, South, East or West |
| `category` | text | Fans, Wires, Water heaters or Stabilisers |
| `ordered` | bigint |  |
| `shipped` | bigint |  |
| `fill_rate_pct` | numeric | Invoiced ÷ ordered × 100 |

### `rpt.lane_freight` (view)
Freight per unit by month, plant-to-warehouse lane and category.

| Column | Type | Meaning |
|---|---|---|
| `month` | text | Calendar month, text YYYY-MM |
| `from_plant` | text | HDW Haridwar, BDI Baddi, HSR Hosur |
| `to_warehouse` | text | WN Gurugram, WS Bengaluru, WE Kolkata, WW Bhiwandi |
| `category` | text | Fans, Wires, Water heaters or Stabilisers |
| `units` | bigint |  |
| `freight` | numeric |  |
| `freight_per_unit` | numeric |  |

### `rpt.margin_bridge` (view)
Month-on-month change in gross margin split into volume, mix, price, cost and returns; the five add up exactly to change.

| Column | Type | Meaning |
|---|---|---|
| `month` | text | Calendar month, text YYYY-MM |
| `scope` | text | All = whole company; otherwise a region |
| `category` | text | Fans, Wires, Water heaters or Stabilisers |
| `margin_prev` | numeric |  |
| `margin_now` | numeric |  |
| `volume` | numeric |  |
| `mix` | numeric |  |
| `price` | numeric |  |
| `cost` | numeric |  |
| `returns` | numeric |  |
| `change` | numeric |  |

### `rpt.margin_bridge_long` (view)
The margin bridge with one row per effect, for the Power BI waterfall.

| Column | Type | Meaning |
|---|---|---|
| `month` | text | Calendar month, text YYYY-MM |
| `scope` | text | All = whole company; otherwise a region |
| `category` | text | Fans, Wires, Water heaters or Stabilisers |
| `effect` | text |  |
| `effect_order` | integer | Sort order of the effect in the waterfall |
| `value` | numeric |  |

### `rpt.margin_by_category` (view)
Gross and contribution margin % by month and category (ratio of totals).

| Column | Type | Meaning |
|---|---|---|
| `month` | text | Calendar month, text YYYY-MM |
| `category` | text | Fans, Wires, Water heaters or Stabilisers |
| `net_sales` | numeric |  |
| `gross_margin` | numeric | Net sales − cost at standard |
| `contribution` | numeric | Gross margin − freight |
| `gross_margin_pct` | numeric |  |
| `contribution_pct` | numeric |  |

### `rpt.margin_by_channel` (view)
Full-year gross margin %, freight % and contribution % by channel.

| Column | Type | Meaning |
|---|---|---|
| `channel` | text | Distributor, Modern retail, E-commerce or Institutional |
| `units` | numeric |  |
| `net_sales` | numeric |  |
| `gross_margin_pct` | numeric |  |
| `freight_pct` | numeric |  |
| `contribution_pct` | numeric |  |

### `rpt.month_end_invoices` (view)
Invoices and value billed in the last four days of each month (cut-off check).

| Column | Type | Meaning |
|---|---|---|
| `month` | text | Calendar month, text YYYY-MM |
| `billing_date` | date |  |
| `invoices` | bigint |  |
| `net_value` | numeric | Value after discount; negative on credit notes |

### `rpt.plant_cost` (view)
Actual vs standard cost, cost per unit and utilisation by line and month.

| Column | Type | Meaning |
|---|---|---|
| `plant` | text | HDW Haridwar, BDI Baddi, HSR Hosur |
| `line` | text | Production line (ref.lines) |
| `category` | text | Fans, Wires, Water heaters or Stabilisers |
| `month` | text | Calendar month, text YYYY-MM |
| `planned_units` | bigint |  |
| `units` | bigint |  |
| `actual_material` | numeric |  |
| `actual_conversion` | numeric |  |
| `std_material` | numeric |  |
| `std_conversion` | numeric |  |
| `material_variance` | numeric |  |
| `conversion_variance` | numeric |  |
| `actual_cost_per_unit` | numeric |  |
| `std_cost_per_unit` | numeric |  |
| `conversion_per_unit` | numeric |  |
| `machine_hours` | numeric |  |
| `available_hours` | numeric(8,1) |  |
| `downtime_days` | integer |  |
| `utilisation_pct` | numeric | Machine hours used ÷ machine hours available × 100 |

### `rpt.reconciliation_summary` (view)
Billing vs ledger by month with status (Matched or Difference).

| Column | Type | Meaning |
|---|---|---|
| `month` | text | Calendar month, text YYYY-MM |
| `billing_net_sales` | numeric |  |
| `ledger_revenue` | numeric |  |
| `difference` | numeric |  |
| `status` | text | Matched or Difference |

### `rpt.return_rates` (view)
Units returned ÷ units invoiced by product, plant and the month the goods were invoiced.

| Column | Type | Meaning |
|---|---|---|
| `material` | text | Product code (ref.materials) |
| `description` | text |  |
| `plant` | text | HDW Haridwar, BDI Baddi, HSR Hosur |
| `invoice_month` | text | Month of the original invoice (for credit notes, not the month the credit note was raised) |
| `units_invoiced` | bigint |  |
| `units_returned` | bigint |  |
| `return_rate` | numeric | Units returned ÷ units invoiced (0–1) |
| `value_returned` | numeric |  |

### `rpt.returns_margin` (view)
Gross margin lost to credit notes by month, scope and category.

| Column | Type | Meaning |
|---|---|---|
| `month` | text | Calendar month, text YYYY-MM |
| `scope` | text | All = whole company; otherwise a region |
| `category` | text | Fans, Wires, Water heaters or Stabilisers |
| `returns_margin` | numeric |  |

### `rpt.revenue_reconciliation` (view)
Billing net sales vs ledger revenue by month and category.

| Column | Type | Meaning |
|---|---|---|
| `month` | text | Calendar month, text YYYY-MM |
| `category` | text | Fans, Wires, Water heaters or Stabilisers |
| `billing_net_sales` | numeric |  |
| `ledger_revenue` | numeric |  |
| `difference` | numeric |  |

### `rpt.risk_opportunity` (view)
Risk and opportunity register; every value is calculated from the views above.

| Column | Type | Meaning |
|---|---|---|
| `id` | text |  |
| `type` | text |  |
| `project` | text |  |
| `item` | text |  |
| `value_inr` | numeric | Value in INR for the year unless the basis says otherwise |
| `basis` | text |  |
| `owner` | text |  |
| `action` | text |  |

### `rpt.sales_lines` (materialized view · 156,494 rows)
Materialized view. One row per billing line with product, customer, margin and freight; the base of every sales metric. Refresh after loading.

| Column | Type | Meaning |
|---|---|---|
| `billing_type` | text | F2 = invoice, G2 = credit note |
| `billing_doc` | bigint |  |
| `item` | integer |  |
| `billing_date` | date |  |
| `month` | text | Calendar month, text YYYY-MM |
| `invoice_month` | text | Month of the original invoice (for credit notes, not the month the credit note was raised) |
| `customer` | text | Customer code (ref.customers) |
| `channel` | text | Distributor, Modern retail, E-commerce or Institutional |
| `region` | text | North, South, East or West |
| `material` | text | Product code (ref.materials) |
| `category` | text | Fans, Wires, Water heaters or Stabilisers |
| `segment` | text | Economy, Mid or Premium |
| `plant` | text | HDW Haridwar, BDI Baddi, HSR Hosur |
| `ordered_qty` | integer | Quantity the customer ordered; quantity is what was invoiced |
| `quantity` | integer |  |
| `list_price` | numeric(12,2) |  |
| `discount_pct` | numeric(5,2) | Discount given on the line, % of list price |
| `gross_value` | numeric(14,2) |  |
| `discount_value` | numeric |  |
| `net_value` | numeric(14,2) | Value after discount; negative on credit notes |
| `cost_at_standard` | numeric(14,2) | Quantity × standard cost for the billing month |
| `gross_margin` | numeric | Net sales − cost at standard |
| `freight` | numeric(12,2) |  |
| `contribution` | numeric | Gross margin − freight |

### `rpt.sales_monthly` (view)
Units, gross sales, discount, net sales, COGS, gross margin, freight and contribution by month, category, region and channel.

| Column | Type | Meaning |
|---|---|---|
| `month` | text | Calendar month, text YYYY-MM |
| `category` | text | Fans, Wires, Water heaters or Stabilisers |
| `region` | text | North, South, East or West |
| `channel` | text | Distributor, Modern retail, E-commerce or Institutional |
| `units_invoiced` | bigint |  |
| `units_returned` | bigint |  |
| `gross_sales` | numeric |  |
| `discount` | numeric |  |
| `net_sales` | numeric |  |
| `cogs` | numeric |  |
| `gross_margin` | numeric | Net sales − cost at standard |
| `freight` | numeric |  |
| `contribution` | numeric | Gross margin − freight |

### `rpt.segment_mix` (view)
Share of each segment (economy, mid, premium) in a category's units, by month and region.

| Column | Type | Meaning |
|---|---|---|
| `month` | text | Calendar month, text YYYY-MM |
| `region` | text | North, South, East or West |
| `category` | text | Fans, Wires, Water heaters or Stabilisers |
| `segment` | text | Economy, Mid or Premium |
| `units` | bigint |  |
| `unit_share` | numeric | Share of the category's units (0–1) |

### `rpt.short_shipments` (view)
Units ordered but not shipped, with the sales and margin lost.

| Column | Type | Meaning |
|---|---|---|
| `month` | text | Calendar month, text YYYY-MM |
| `region` | text | North, South, East or West |
| `category` | text | Fans, Wires, Water heaters or Stabilisers |
| `units_short` | bigint |  |
| `sales_lost` | numeric |  |
| `margin_lost` | numeric |  |

### `rpt.west_competitor_signal` (view)
West: share of field notes about competitor pricing vs premium share of fan units, by month.

| Column | Type | Meaning |
|---|---|---|
| `month` | text | Calendar month, text YYYY-MM |
| `competitor_note_share` | numeric |  |
| `premium_fan_share` | numeric |  |

### `rpt.wh_supply_monthly` (view)
North water heater supply by month: ordered, shipped from each plant, short, Haridwar capacity; feeds the business case.

| Column | Type | Meaning |
|---|---|---|
| `month` | text | Calendar month, text YYYY-MM |
| `north_ordered` | bigint |  |
| `north_from_haridwar` | bigint |  |
| `north_from_hosur` | bigint |  |
| `north_short` | bigint |  |
| `east_from_haridwar` | bigint |  |
| `north_margin_per_unit` | numeric |  |
| `north_std_cost_per_unit` | numeric |  |
| `haridwar_units_made` | bigint |  |
| `haridwar_hours_used` | numeric |  |
| `hours_per_unit` | numeric |  |
| `available_hours` | numeric(8,1) |  |
| `downtime_days` | integer |  |
| `freight_haridwar_to_north` | numeric |  |
| `freight_hosur_to_north` | numeric |  |

### `rpt.wire_cost_monthly` (view)
Wire units, net sales, standard cost, copper cost and copper price by month; feeds the copper what-if.

| Column | Type | Meaning |
|---|---|---|
| `month` | text | Calendar month, text YYYY-MM |
| `units` | bigint |  |
| `net_sales` | numeric |  |
| `cost_at_standard` | numeric | Quantity × standard cost for the billing month |
| `copper_cost` | numeric |  |
| `copper_per_kg` | numeric(10,2) |  |
