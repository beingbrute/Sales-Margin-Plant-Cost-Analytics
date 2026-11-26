-- =====================================================================
-- 01  Schema: SAP-style extracts after cleaning (src/clean_data.py)
--   ref  master data      sd  sales and billing      pp  production
--   mm   stock movements  fi  ledger                 inp inputs from teams and field notes
--   etl  cleaning log     rpt reporting views (02 onwards)
-- =====================================================================
DROP SCHEMA IF EXISTS rpt, etl, inp, fi, mm, pp, sd, ref CASCADE;
CREATE SCHEMA ref; CREATE SCHEMA sd; CREATE SCHEMA pp; CREATE SCHEMA mm;
CREATE SCHEMA fi; CREATE SCHEMA inp; CREATE SCHEMA etl; CREATE SCHEMA rpt;

CREATE TABLE ref.plants (plant TEXT PRIMARY KEY, plant_name TEXT NOT NULL, city TEXT, zone TEXT);
CREATE TABLE ref.lines (plant TEXT REFERENCES ref.plants, line TEXT PRIMARY KEY, category TEXT NOT NULL,
                        fixed_cost_month NUMERIC(14,2) NOT NULL);
CREATE TABLE ref.warehouses (warehouse TEXT PRIMARY KEY, warehouse_name TEXT, city TEXT, region TEXT UNIQUE NOT NULL);
CREATE TABLE ref.materials (
    material TEXT PRIMARY KEY, description TEXT NOT NULL, category TEXT NOT NULL, segment TEXT NOT NULL,
    list_price NUMERIC(12,2) NOT NULL, conversion_std NUMERIC(12,2) NOT NULL, packing NUMERIC(12,2) NOT NULL,
    plant TEXT NOT NULL, line TEXT NOT NULL, machine_hours_per_unit NUMERIC(8,4) NOT NULL, weight_kg NUMERIC(8,2) NOT NULL);
CREATE TABLE ref.bill_of_materials (material TEXT PRIMARY KEY REFERENCES ref.materials,
    copper_kg NUMERIC(8,3), steel_kg NUMERIC(8,3), plastic_kg NUMERIC(8,3));
CREATE TABLE ref.standard_costs (material TEXT REFERENCES ref.materials, valid_from DATE,
    raw_material NUMERIC(12,2), conversion NUMERIC(12,2), packing NUMERIC(12,2), standard_cost NUMERIC(12,2) NOT NULL,
    PRIMARY KEY (material, valid_from));
CREATE TABLE ref.price_list (material TEXT REFERENCES ref.materials, valid_from DATE, list_price NUMERIC(12,2) NOT NULL,
    PRIMARY KEY (material, valid_from));
CREATE TABLE ref.discount_policy (channel TEXT PRIMARY KEY, max_discount_pct NUMERIC(5,2) NOT NULL);
CREATE TABLE ref.customers (customer TEXT PRIMARY KEY, customer_name TEXT, channel TEXT NOT NULL REFERENCES ref.discount_policy,
    region TEXT NOT NULL REFERENCES ref.warehouses (region), city TEXT);
CREATE TABLE ref.commodity_prices (month TEXT PRIMARY KEY, copper_per_kg NUMERIC(10,2), steel_per_kg NUMERIC(10,2),
    plastic_per_kg NUMERIC(10,2));

-- VBRK/VBRP: F2 = invoice, G2 = credit note (negative quantity and value, reference_doc = original invoice)
CREATE TABLE sd.billing (
    billing_type TEXT NOT NULL CHECK (billing_type IN ('F2', 'G2')),
    billing_doc BIGINT NOT NULL, item INT NOT NULL, billing_date DATE NOT NULL,
    customer TEXT NOT NULL REFERENCES ref.customers, material TEXT NOT NULL REFERENCES ref.materials,
    plant TEXT NOT NULL REFERENCES ref.plants, ordered_qty INT NOT NULL, quantity INT NOT NULL,
    list_price NUMERIC(12,2), discount_pct NUMERIC(5,2), gross_value NUMERIC(14,2), net_value NUMERIC(14,2) NOT NULL,
    cost_at_standard NUMERIC(14,2) NOT NULL, freight NUMERIC(12,2) NOT NULL, reference_doc BIGINT, unit TEXT,
    PRIMARY KEY (billing_doc, item));

CREATE TABLE pp.production_orders (
    production_order BIGINT PRIMARY KEY, plant TEXT REFERENCES ref.plants, line TEXT REFERENCES ref.lines,
    material TEXT REFERENCES ref.materials, month TEXT NOT NULL, planned_qty INT, actual_qty INT,
    actual_material_cost NUMERIC(14,2), machine_hours NUMERIC(10,1), actual_conversion_cost NUMERIC(14,2));
CREATE TABLE pp.plant_capacity (plant TEXT REFERENCES ref.plants, line TEXT REFERENCES ref.lines, month TEXT,
    available_hours NUMERIC(8,1), downtime_days INT, fixed_cost NUMERIC(14,2), PRIMARY KEY (line, month));

CREATE TABLE mm.stock_transfers (sto_no BIGINT PRIMARY KEY, from_plant TEXT REFERENCES ref.plants,
    to_warehouse TEXT REFERENCES ref.warehouses, material TEXT REFERENCES ref.materials, quantity INT,
    dispatch_date DATE, receipt_date DATE, freight_cost NUMERIC(12,2));
CREATE TABLE mm.warehouse_stock (warehouse TEXT REFERENCES ref.warehouses, material TEXT REFERENCES ref.materials,
    month TEXT, closing_qty INT, PRIMARY KEY (warehouse, material, month));

CREATE TABLE fi.gl_revenue (fiscal_month TEXT, category TEXT, revenue NUMERIC(16,2), PRIMARY KEY (fiscal_month, category));

CREATE TABLE inp.function_inputs (function TEXT, provided_by TEXT, input TEXT, key TEXT, value NUMERIC(14,3), unit TEXT);
CREATE TABLE inp.field_notes (note_id TEXT PRIMARY KEY, visit_date DATE, region TEXT, channel TEXT, note TEXT NOT NULL);

CREATE TABLE etl.cleaning_log (rule TEXT, dataset TEXT, action TEXT, rows INT, net_value_removed NUMERIC(16,2));
