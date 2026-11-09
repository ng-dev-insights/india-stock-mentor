# Changelog

## 0.3.1 — CAGR fix
- Fixed: CAGR ignored losses in intermediate years (100 → −50 → 400 showed "100%, Comfortable"). CAGR is now undefined if any year is zero or negative, with a new `loss_in_an_intermediate_year` red flag
- Calculator states its EPS basis from the data (`eps_basis`: `ttm` or `annual` + `eps_period`); validator check E10 rejects a mismatch
- README no longer overclaims per-figure sourcing; sector classification of the example explained
- Tests: 43 → 45

## 0.3.0 — print, accessibility, free cash flow
- Print / PDF stylesheet: light paper even when the reader uses dark mode; no clipped tables or charts; rows, events and cards don't split across pages; chart stays with its heading; sliders hidden, results kept
- Growth chart has a screen-reader data table (`aria-describedby`)
- Free cash flow: optional `capex_cr` gives `fcf_latest_cr`, `fcf_total_cr`, `capex_to_ocf_pct`, `fcf_yield_pct` and a `free_cash_flow_negative_over_period` flag; crore values shown as ₹ with Indian grouping
- `publish_report.py --dry-run` runs every check without touching the output; publish summary shows languages and file sizes
- Tests: 37 → 43

## 0.2.2 — reliability fixes from the V2.1 review
- Malformed nested content (`simulator`, `scenarios.cases`, `history`, etc.) is rejected with a message instead of a traceback
- Language codes restricted to BCP-47 style (`en`, `mr`, `hi`, `mr-IN`); checked in the builder and again before any filename is created
- Publishing rollback: if swapping in the new report fails, the previous report is restored to its original place
- Consistency checker compares signed numbers (hyphen and Unicode minus, accounting parentheses); ranges like 38–40% and FY2025-26 are not read as negatives
- ROCE uses average capital employed when `equity_prev_cr` and `debt_prev_cr` are given
- Cash conversion aligns cash flow with profit by fiscal-year labels (`years`, `ocf_years`) and records the periods used
- Tests: 31 → 37 (rollback and pledge tests verified by reintroducing each bug)

## 0.2.1 — integrity release
Guarantees: right denominator and period for every figure; no inconsistent numbers, dates or scenarios pass validation; a report is written only when every check passes.
- Fixed: validator used current shares instead of `eps_shares_cr`, rejecting correct reports (regression from 0.2.0)
- `eps_shares_cr` must be > 0 (0 used to fall back silently to current shares)
- Content schema validation: unknown keys, wrong types, invalid event tags, quiz shape, label typos and broken label placeholders all fail with a message
- Calculator values must fit the sliders; sliders and validation share one set of limits (`SIM_LIMITS`)
- Header date must match day, month and year (English, Marathi and Hindi month names)
- E9: no P/E scenarios or calculator when the last 4 quarters were loss-making
- `publish_report.py`: rejects two files with the same language; publishes atomically (staging folder swapped in; existing report untouched on failure)
- Tests: 24 → 31

## 0.2.0 — hardening after external code review
- Strict input validation: finite numbers only; no negative debt, cash, interest or dividends; holdings and pledges 0–100%; matching year counts
- Fixed: pledge range bar disagreed with its flag for small pledges (0–0.5%)
- New red flags: profit fell two years in a row; sales up but profit down in the latest year; loss-making over the last 4 quarters
- TTM losses are reported explicitly (no TTM P/E, no PEG) instead of being silently skipped
- Optional `eps_shares_cr` (weighted diluted shares) and `equity_prev_cr` (average-equity ROE); cash conversion needs 2+ years before giving a signal
- Report header price and date mismatches are now hard errors (E7, E8)
- Scenario and calculator inputs fully validated (years, growth > −100%, P/E > 0)
- New `publish_report.py`: one command, nothing published unless every check passes
- Tests: 15 → 24, including a sweep of every threshold (verified to catch the pledge bug)

## 0.1.0 — first public version
- Four modes: explain a stock, teach a concept, beginner path, portfolio learning review
- Ratio engine with a single threshold table; input validation; negative-equity safety
- HTML report: health check, growth chart (handles loss years), recent events with kind/confidence, plain-language scenarios, P/E calculator, quiz
- Validators: `validate_report.py` (numbers inside a report), `check_consistency.py` (across languages)
- English and Marathi example; Hindi term table
