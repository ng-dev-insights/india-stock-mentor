# Example: Acutaas Chemicals Ltd (NSE: ACUTAAS)

A complete worked example produced with the skill. **Data as of 6 Nov 2026** (price) and the Q2 FY27 results (27 Oct 2026). It is an illustration of the method, not current data and not a recommendation.

- `input.json`: figures entered into `ratios.py` (₹ crore; shares in crore)
- `ratios.json`: computed output
- `content_en.json`: canonical report text (English)
- `content_mr.json`: Marathi, derived from the English file; passes `check_consistency.py`
- `report_en.html`, `report_mr.html`: rendered reports (open in a browser)

## Why `sector_type` is `general`, not `cyclical`
Most of Acutaas's revenue comes from pharma intermediates made for drug companies (contract and custom manufacturing). Demand follows drug pipelines more than the economic cycle, so it isn't treated like commodity chemicals, whose profits swing with prices. The smaller specialty chemicals segment (battery and semiconductor chemicals) is more cyclical; the report flags its weakness as a recent event instead. Treat this as a judgment call: if specialty chemicals grows into a large share of revenue, revisit it.
