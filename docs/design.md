# Design: Sales, Margin & Plant Cost Analytics

> **All data in this project is synthetic.** Orvane Electricals, its plants, products, customers and amounts are invented to demonstrate the analysis. Table layouts follow common SAP structures so the work resembles an ERP extract; no real SAP system was used. Currency: INR.

---

## 1. The business scenario

**Orvane Electricals** (fictional) makes and sells consumer electricals in India: fans, wires and cables, water heaters and voltage stabilisers.

```
Raw materials (copper, steel, plastics) bought at monthly market prices
        ↓
3 plants make the products (each product in one plant, except water heaters, made in two)
        ↓
Supply chain: finished goods move from plants to 4 regional warehouses (stock, dispatches, freight)
        ↓
Sales through 4 channels: distributors, modern retail, e-commerce, institutional
        ↓
Billing documents (invoices, credit notes for returns) by customer, region and channel
        ↓
Revenue, discounts, cost of goods sold at standard, freight → gross and contribution margin
```

The COO's office wants a reliable view of sales and margin, an explanation of what moved margin each month, the cost and utilisation of each plant, and analysis to support operating decisions.

**Period:** April 2025 to March 2026 (financial year 2025-26). **Regions:** North, South, East, West.

---

## 2. Data (SAP-style extracts)

| Dataset | Based on | Grain | Key fields |
|---|---|---|---|
| `plants` | T001W | One per plant | Plant code, name, city, lines |
| `materials` | MARA / MARC | One per product | Material, description, category, segment (economy / mid / premium), producing plant |
| `standard_costs` | Cost estimate (CK11) | One per product per cost version | Raw material, conversion and packing cost per unit, valid from |
| `price_list` | Condition records (PR00) | One per product per price version | List price per unit, valid from |
| `discount_policy` | Condition records (K007) | One per channel | Maximum discount % allowed |
| `customers` | KNA1 / KNVV | One per customer | Customer, region, channel, city |
| `billing` | VBRK / VBRP | One per billing line | Billing doc, type (invoice / credit note), date, customer, material, quantity, list price, discount, net value, cost at standard, freight |
| `production_orders` | AFKO / AFPO | One per order | Plant, line, material, month, planned and actual quantity, actual material and conversion cost, machine hours |
| `plant_capacity` | Work centres (CRHD) | One per line per month | Available machine hours, fixed conversion cost |
| `commodity_prices` | Purchasing info records | One per commodity per month | Copper, steel, plastics price per kg |
| `stock_transfers` | Stock transport orders (STO) | One per shipment | Plant to regional warehouse, material, quantity, dispatch and receipt dates, freight cost |
| `warehouse_stock` | Stock overview (MB52) | One per warehouse, product and month-end | Closing stock quantity |
| `gl_revenue` | General ledger (FAGLFLEXT) | One per month and category | Revenue booked in the ledger, used for reconciliation |
| `function_inputs` | Templates filled by teams | One per input | Sales forecast (sales), line capacity plan (plants), freight rates (supply chain), cost assumptions (finance) |
| `field_notes` | Sales team visit notes | One per note | Region, channel, date, free-text note from a distributor or retailer visit |

**Volume:** 52 products, 3 plants (8 lines), 4 warehouses, 400 customers, 156,674 billing lines as extracted (151,739 invoice lines and 4,755 credit-note lines, plus 180 duplicates), 744 production orders, 5,068 stock transfers and 1,200 field notes over 12 months.

**The extracts are not clean**, as ERP extracts rarely are: duplicate billing lines, materials with old codes, customers with region missing, dates in two formats and quantities with the wrong unit. Cleaning rules are documented, and every row removed or changed is counted.

---

## 3. Metric definitions

| Metric | Definition |
|---|---|
| **Gross sales** | Quantity × list price |
| **Discount** | Gross sales − net sales |
| **Net sales** | Invoice net value − credit notes |
| **Cost of goods sold (COGS)** | Quantity × standard cost of the period |
| **Gross margin** | Net sales − COGS; **gross margin %** = gross margin ÷ net sales |
| **Contribution margin** | Gross margin − freight |
| **Price effect** | Change in net price per unit × this month's volume |
| **Volume effect** | Change in total units × last month's average margin per unit |
| **Mix effect** | Change in product mix at last month's margin per unit of each product |
| **Cost effect** | Change in standard cost per unit × this month's volume |
| **Plant cost per unit** | Actual production cost ÷ units produced |
| **Cost variance** | Actual cost − standard cost, split into material and conversion |
| **Capacity utilisation** | Machine hours used ÷ machine hours available |
| **Return rate** | Credit-note quantity ÷ invoiced quantity |
| **Fill rate** | Quantity invoiced ÷ quantity ordered (short shipments lower it) |
| **Days of stock** | Closing stock ÷ average daily sales |
| **Freight per unit** | Freight cost ÷ units shipped, by plant–warehouse lane |

Every metric is defined once in SQL views and reused by Excel and Power BI.

---

## 4. Planted problems (answer key kept separately)

| Months | Planted situation | Expected finding |
|---|---|---|
| Jul–Sep | Copper price rises about 18%; wire prices are not raised until October | Wires gross margin falls; cost effect negative; partly recovered after the October price increase |
| Apr–Jun | South fan sales shift towards economy models in summer | Fans margin % falls in the South through the mix effect, while volume rises |
| Oct–Dec | East region distributors given discounts above the channel policy | Price effect negative in the East; discount leakage sized against policy |
| Nov–Dec | A stabiliser line at the Baddi plant is down for 3 weeks | Utilisation drops; conversion cost per unit up because fixed cost is spread over fewer units |
| Jan–Feb | A quality issue on one water heater model (WH006) from the Hosur plant | About 6% of the units invoiced in January–February come back (normal: under 1%); credit notes reduce net sales |
| Full year | E-commerce grows faster than other channels and carries higher freight | Gross margin % holds but contribution margin % is lower in e-commerce |
| Dec–Jan | 214 invoices dated 28–31 December are booked in the ledger in January (cut-off) | Billing and ledger revenue do not reconcile for December and January; difference explained |
| Oct–Jan | Water heaters for the North are shipped from Hosur (south) after a Haridwar stock shortfall | Freight per unit on the Hosur–North lane jumps; days of stock low in the North warehouse |
| Full year | Field notes repeatedly mention a competitor's cheaper BLDC fan in the West | Theme found in field notes matches a fall in West premium fan volume |

Everything else is normal variation (seasonality: fans peak in summer, water heaters in winter).

---

## 5. Analysis and decisions

The work is organised as **three COO's office projects run side by side**, each with its own fact base, analysis and recommendation, sharing one data model:

| Project | Question | Uses |
|---|---|---|
| **P1 Margin recovery** | Why did gross margin fall, and what recovers it? | Price-volume-mix-cost bridge, discount leakage, wire price what-if |
| **P2 Plant and supply chain footprint** | Should stabiliser production stay at Baddi, and should water heaters be stocked closer to the North? | Plant cost per unit, utilisation, freight by lane, business case |
| **P3 Channel profitability** | Is e-commerce growth worth it after freight and returns? | Contribution margin by channel, return rates, field notes |

Each project starts from an **inputs register**: what each function provided (sales forecast, plant capacity plan, freight rates, cost assumptions), who owns it, and how it was checked against the data.

1. **Sales:** trends by category, region, channel and customer; seasonality.
2. **Margin:** gross and contribution margin by category, region and channel; month-on-month **price-volume-mix-cost bridge**.
3. **Plants:** cost per unit, actual vs standard cost variance, capacity utilisation by line.
4. **Root causes, risks and opportunities:** each planted problem traced to its cause and sized in ₹, plus a register of risks (e.g. copper exposure) and opportunities (e.g. discount recovery) with owner and value.
5. **Supply chain:** fill rate, days of stock and freight per unit by lane.
6. **Reconciliation:** billing register vs ledger revenue each month, with every difference explained.
7. **Business case (Excel):** for example, moving the under-used Baddi stabiliser line to another plant, or a wire price increase what-if.
8. **Market brief:** industry trends and competitor moves from public annual reports, investor presentations and earnings-call transcripts of listed Indian consumer electricals companies, with sources cited, and how Orvane's numbers compare. **Field insights:** themes in 1,200 sales field notes, tagged with a local language model (Ollama) and checked by hand on a sample before use.
9. **Leadership deck:** 6–8 slides, insight first, method second.
10. **Ad hoc analysis log:** 10 short questions of the kind a COO's office asks (for example "why did wire margin fall in August?", "which 20 customers drive East discounts?"), each answered with the query, the result and a two-line answer, and timed.
11. **Monthly business review pack:** the data points for a monthly review, refreshed by one script run and reconciled to the ledger before it is published.
12. **Knowledge base:** reusable templates (analysis request, business case, review pack, deck), metric definitions, data dictionary and an SOP for the monthly refresh.

---

## 6. Deliverables

| Output | Tool |
|---|---|
| Schema, metric views, reconciliation | PostgreSQL |
| Data generator, cleaning, loader, monthly refresh, tests | Python (pandas, pytest) |
| Field-note themes | Python + local LLM (Ollama), checked by hand on a sample |
| Business case and what-if | Excel |
| Sales, margin and plant dashboard | Power BI |
| Monthly business review pack | Python + Excel, refreshed by one script |
| Ad hoc analysis log | SQL + Markdown |
| Market brief | Markdown, with cited public sources |
| Leadership deck | PowerPoint |
| Templates, SOP, data dictionary | Markdown + Excel |

## 7. Out of scope

A real SAP or ERP system, real company data, and work with real sales, plant, supply chain or finance teams (their inputs are simulated in the inputs register). The project shows the analysis, not experience inside a manufacturing company.
