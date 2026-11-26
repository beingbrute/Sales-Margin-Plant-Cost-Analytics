# SOP: monthly refresh and business review pack

How the COO's office numbers are refreshed each month, checked, and published. Written for this project's fictional company (Orvane Electricals, synthetic data); the steps are the ones the scripts in this repo actually run.

| | |
|---|---|
| **Purpose** | Publish one reconciled set of sales, margin, plant and supply chain numbers for the monthly review |
| **Owner** | Business analyst, COO's office |
| **When** | Working days 1–4 after month end; review meeting on working day 5 |
| **Inputs** | ERP extracts (billing, production orders, stock transfers, warehouse stock, ledger revenue), function inputs (templates/function_inputs_template.xlsx), sales field notes |
| **Outputs** | Review pack `reviews/review_pack_<month>.xlsx`, refreshed Power BI report, updated risk and opportunity register, ad hoc log |

## Timeline

| Day | Step | Who |
|---|---|---|
| WD 1 | Receive ERP extracts; chase function inputs not yet received | Analyst |
| WD 2 | Clean, load, run tests | Analyst |
| WD 2 | Reconcile billing to ledger; investigate any difference with finance | Analyst, finance controller |
| WD 3 | Build the review pack, refresh Power BI, update the register | Analyst |
| WD 4 | Check the pack against last month and the inputs register; send to the COO's office | Analyst |
| WD 5 | Monthly review; actions recorded with owners | COO's office |

## Steps

All commands run from the project folder. `--port 5433` is the laptop's PostgreSQL port; the password is typed when asked and never stored.

### 1. Put the new extracts in place
Save the month's extracts in `data/raw/` with the same file names and columns as before. Save the completed function inputs as `data/raw/function_inputs.csv` (one row per input: function, provided_by, input, key, value, unit).

In this project the extracts are generated, so this step is `python src/generate_data.py`.

### 2. Clean
```
python src/clean_data.py
```
Check the five rule counts printed (C1 dates, C3 old material codes, C4 metres, C2 duplicates, C5 missing region). **A count that moves a lot from last month is a question for the ERP team before going on**: it usually means an extract changed.

### 3. Load
```
python src/load_data.py --port 5433
```
Every table prints its row count. `sd.billing` should be close to last month's run plus one month of lines.

### 4. Tag new field notes (only if new notes arrived)
```
python src/tag_field_notes.py
python src/tag_field_notes.py --retry
python src/load_data.py --port 5433
```
Needs Ollama running with `qwen3:4b`. After tagging, mark 40 notes in `data/derived/field_notes_hand_check.csv` (Y/N) and run `python src/tag_field_notes.py --score`. If the hand check is below 90%, do not use the themes in the pack; note it and review the prompt.

### 5. Test
```
python -m pytest -s -v tests --port 5433
```
All tests must pass. The tests check that the data is whole (no duplicates, every line has a customer and product, no line above 100% utilisation), that an independent pandas recalculation matches the SQL views, and that the review pack refuses an unexplained difference. **A failing test stops the refresh.**

### 6. Reconcile and build the review pack
```
python src/build_review_pack.py --month <YYYY-MM> --port 5433
```
The script reconciles billing to the ledger for the month first:
- **Matched:** the pack is built.
- **Explained (cut-off):** the difference reverses exactly in the next or previous month; the pack is built with the difference stated on the summary page.
- **STOP:** any other difference. The pack is not built. Take the amount to the finance controller, find the cause, and re-run after it is corrected in the ledger or the extract.

### 7. Refresh the reporting outputs
```
python src/export_reporting.py --port 5433
python src/build_business_case.py
python src/build_adhoc_log.py --port 5433
```
Then open `powerbi/orvane_coo_office.pbix` and click **Refresh**. Check the Checks page: every check must show the same value as `python src/show.py <topic> --port 5433`.

### 8. Review before sending
- [ ] Net sales for the month within the range expected from the sales forecast in the inputs register (MAPE has been 4.7–6.4% by category)
- [ ] Each change above ₹50 lakh in the margin bridge has a one-line reason
- [ ] Every risk and opportunity in the register has an owner and an action
- [ ] Assumptions in the inputs register compared with actuals (copper price, planned working days); differences flagged
- [ ] Power BI Checks page matches `show.py`
- [ ] File names carry the month; last month's pack is not overwritten

### 9. Send and record
Send the pack and the Power BI link to the COO's office. After the review, record the actions in the register (owner, date, value) and add any questions asked in the meeting to the ad hoc log.

## When something goes wrong

| Problem | What to do |
|---|---|
| Password prompt hidden during tests | Run pytest with `-s` |
| `could not connect to server` | Start the PostgreSQL service and check the port |
| Load fails on a type (for example "90000015.0") | A column with blanks was read as decimal; check the cleaning step for that column |
| Review pack STOP | Do not publish. Take the amount to finance; publish only after it is explained |
| Many field notes "Unclassified" | Look at `data/derived/field_note_answers_raw.csv` to see what the model answered, then fix the matching or the prompt |
| A number in Power BI differs from `show.py` | Check relationships and filters; the margin bridge must be filtered to scope = All for company totals |
