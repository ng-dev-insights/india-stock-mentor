# Stock Analysis Framework (Mode A)

Walk through these six questions in order. Each one maps to a few numbers; the script computes them. Explain each answer in plain language before moving on. The order matters: a beginner who learns "first understand the business, then the numbers, then the price" has learned the most important habit in investing.

## Contents
1. What does the business do?
2. Is it growing?
3. Is it profitable, and is the profit real?
4. How much debt?
5. Is the price expensive?
6. Who owns it, and any governance red flags?
7. Sector exceptions (banks, NBFCs, insurers, cyclicals, new-age/loss-making)
8. Meaning of each `band_note` from the script
9. Where to find each number

---

## 1. What does the business do?
- What do they sell, to whom, and how do they earn money? Explain with an everyday comparison ("like a toll road", "like a kirana store with 5,000 branches").
- Where does most revenue come from (segments, India vs exports)?
- Why might customers keep choosing them (brand, network, cost, licences)? This is the "moat". Keep it concrete.
- If you cannot explain the business simply, say so: that itself is a lesson ("invest in what you understand").

## 2. Is it growing?
- Revenue CAGR and profit CAGR over 3–5 years (`revenue_cagr_pct`, `profit_cagr_pct`).
- Compare with inflation (~4–6% in recent years in India): growth below inflation means the business is shrinking in real terms.
- Steady growth beats one spectacular year. Look at the year-by-year series, not just the CAGR.
- Red flag: sales growing but profit falling (script flags `sales_growing_but_profit_falling`).

## 3. Is it profitable, and is the profit real?
- Net margin: how many rupees of profit from each ₹100 of sales. Varies hugely by industry (supermarket ~2–5%, software ~15–25%), so compare with peers, not a fixed number.
- ROE: profit earned on shareholders' own money. ~15%+ is generally good for non-financial companies, but a high ROE driven by heavy debt is lower quality, so read it with debt-to-equity.
- ROCE: profit earned on all capital (owners' + borrowed). One of the most useful measures of business quality for non-financial companies, but compare it within the same industry: capital-heavy businesses naturally show lower ROCE.
- Cash conversion: operating cash flow ÷ net profit over several years. Net profit includes accounting estimates and accruals (sales booked but not yet collected, for example); operating cash flow tests whether that profit is turning into real cash. The script uses total cash ÷ total profit over the years, which is steadier than averaging each year's ratio. Below ~0.8 for years deserves a question; below 0.5 is a red flag.

- **Free cash flow (FCF)** = operating cash flow − capex (money spent on plants, machines, buildings). Analogy: a family's take-home pay minus what it spends on a new house extension. Positive FCF means the business funds its own growth; negative FCF means it needs outside money (debt, new shares) or its savings. Negative FCF is **not automatically bad**: a company building new plants can burn cash for a few years. The questions are what the capex is for, how it is funded (watch for rising debt or new share issues), and whether operating cash flow grows once the plants run. Pass `capex_cr` with `operating_cash_flow_cr` (same years, `ocf_years`) to get `fcf_latest_cr`, `fcf_total_cr`, `capex_to_ocf_pct` and `fcf_yield_pct`.

## 4. How much debt?
- Debt-to-equity (D/E). Analogy: a family's loans compared with its savings. Below 0.5 comfortable, 0.5–1 watch, above 1 concern for most non-financial businesses; capital-heavy sectors (power, infra, telecom) normally carry more.
- Interest coverage: operating profit ÷ interest. How many times over the company can pay its interest. Below ~2 is fragile; below 1.5 is a red flag.
- Net debt negative = more cash than debt ("net cash"). Usually a sign of safety.

## 5. Is the price expensive?
- P/E: price ÷ earnings per share, said as "investors pay ₹X for every ₹1 of yearly profit". Analogy: a flat costing ₹50 lakh that earns ₹2 lakh rent a year is priced at 25 times its rent.
- **Don't teach P/E as "years to earn the money back".** It isn't: the company keeps most profit instead of paying it out, and profit changes. Use the "₹ per ₹1 of profit" wording everywhere, including scenarios and the calculator, so the learner meets one idea, not two.
- A high P/E is not automatically bad: the market may expect fast growth. Compare with (a) the company's own past P/E, (b) its closest business peers, (c) its growth rate.
- **Choose peers by business model, not by a website's sector label.** Aggregator "sector P/E" figures often lump together very different businesses. Name 2–3 companies that actually do similar work and show their P/E next to the broad sector figure. If the stock is expensive versus the market but in line with close peers, say exactly that.
- PEG = P/E ÷ profit growth %. Around 1 is often called fair. Caution: it uses past growth; future growth is a guess.
- P/B matters most for banks and financial companies.
- Always teach: "cheap" can be cheap for a reason (value trap), and "expensive" can stay expensive for years. Nobody can tell where the price goes next.

## 6. Who owns it, and any governance red flags?
- Promoter holding: the founders' or owning group's stake. High holding shows skin in the game; very high (close to the 75% limit for listed companies) reduces free float.
- Promoter pledge: promoters borrowing against their shares. If the price falls, lenders can sell those shares, pushing the price down further. Any pledge deserves a question; above ~25% is a red flag.
- Promoters reducing stake sharply over a few quarters: ask why.
- Other governance checks the mentor can teach: auditor resignations, many related-party transactions, frequent equity dilution, SEBI orders against the company or promoters, qualified audit opinions. Search news and exchange filings for these.

## 7. Sector exceptions

**Banks and NBFCs** (`sector_type`: bank/nbfc). Debt is their raw material, so D/E, ROCE and interest coverage don't apply. Use instead:
- Gross NPA and Net NPA % (bad loans). Lower is better; rising NPA is the key warning sign.
- CASA ratio (banks): share of cheap current and savings deposits. Higher means cheaper funding.
- Capital adequacy ratio (CRAR/CAR): the safety buffer; RBI sets the minimum.
- Net interest margin (NIM): the lending spread.
- ROA (~1%+ is decent for a bank) and ROE (~12–15%+ good).
- P/B, not P/E, is the main valuation measure.

**Insurance**: different metrics again (VNB margin for life insurers, combined ratio for general insurers). Explain at a high level and say these need specialised study.

**Cyclicals** (metals, cement, auto, commodity chemicals, commodities). Specialty and contract-manufacturing chemical companies (pharma intermediates, CDMO) are usually not treated as cyclical, because demand follows customers' product pipelines more than commodity prices; state the classification and the reason in the report, since it is a judgment call: profits swing with the economy. A low P/E at the peak of the cycle is often a trap, because profits are about to fall. Look at 7–10 years of profit, not 3.

**Loss-making and new-age companies**: P/E is undefined. Explain revenue growth, path to profit, and cash runway (how long the cash lasts at current losses). Be direct that the risk is higher.

**PSUs (government-owned)**: note that the government's priorities (policy, dividends, social goals) can matter as much as profit.

## 8. Meaning of each `band_note` from the script

| band_note | What to tell the learner |
|---|---|
| market_cap_size | Size of the company. Rough Indian convention: large cap ~top 100 companies, mid cap 101–250, small cap beyond (SEBI/AMFI categorisation). Smaller = usually more volatile. |
| eps | Profit per share. Mainly an input for P/E. |
| pe_compare_with_sector_and_growth | Compare with sector peers and growth; no universal "good" P/E. |
| pe_ttm_uses_last_4_quarters | P/E on the latest 4 quarters of profit (TTM); usually more current than the annual P/E. |
| pe_undefined_loss_making | No profit, so no P/E. Higher risk; look at growth and cash runway. |
| pb_key_for_financials / pb_secondary_for_non_financials | P/B matters for banks; less useful for asset-light businesses. |
| growth_vs_inflation | Compare growth with inflation. |
| fcf_cash_left_after_investing | Operating cash flow minus capex in the latest year. |
| fcf_total_over_period | Free cash flow added up over the years shown; negative means the company spent more than it generated. |
| share_of_operating_cash_reinvested | How much of the cash from operations went back into plants and equipment. |
| fcf_yield_compare_fd | Latest free cash flow ÷ market cap; compare with an FD rate to sense how much cash the price buys. |
| peg_rough_guide_past_growth_not_future | PEG uses past growth; the future may differ. |
| margin_varies_by_industry | Compare with peers. |
| roe_with_debt_check | Good ROE should not come mainly from debt. |
| roe_financials_12_15_good | For lenders, ~12–15%+ is good. |
| roce_core_quality | Core business quality. |
| debt_family_emi_analogy | Like a family's EMI burden. |
| net_cash_if_negative | Negative = more cash than debt. |
| interest_coverage_times | Times over the interest can be paid. |
| profit_should_become_cash | Real profit becomes cash over time. |
| dividend_yield_compare_fd | Compare with FD rates; dividends are taxable at slab rate. |
| payout_over_100_unsustainable | Paying more than profit can't last. |
| pledge_risk_forced_selling | Lenders can sell pledged shares in a fall. |
| promoter_holding_context | Skin in the game, read with changes over time. |
| check_units_… (note) | Inputs probably in wrong units; recheck before explaining anything. |

## 9. Where to find each number

- **Screener.in** (free): 10-year P&L, balance sheet, cash flow, ratios, shareholding, peers. Easiest for beginners; use as secondary and cross-check key figures.
- **Company investor-relations page**: annual reports, quarterly results, investor presentations. Primary source.
- **NSE/BSE websites**: price, corporate announcements, shareholding pattern, pledge data. Primary source.
- **Broker apps (Zerodha, Groww, etc.)**: price and basic ratios; fine for quick checks.

Teach the learner to find at least one number themselves in every stock explanation. That is how they stop depending on anyone, including you.
