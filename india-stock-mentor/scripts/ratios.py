#!/usr/bin/env python3
"""
Deterministic ratio calculator for India Stock Mentor.

Usage:
    python3 ratios.py input.json            # prints JSON result
    python3 ratios.py input.json --pretty   # indented output

All money values in the SAME unit (use ₹ crore, as Indian reports do),
except per-share values (price, dividend_per_share) which are in ₹.
Every field is optional; ratios are computed only when their inputs exist.

Input fields:
{
  "company": "Example Ltd",
  "as_of": "2026-11-09",              # date of the price
  "sector_type": "general",          # "general" | "bank" | "nbfc" | "insurance" | "cyclical"
  "price": 1500.0,                   # ₹ per share
  "shares_outstanding_cr": 100.0,    # shares, in crore (e.g. 100 = 1,000,000,000 shares)
  "revenue_cr": [800, 900, 1000, 1150],     # oldest -> latest, yearly
  "net_profit_cr": [80, 95, 110, 130],      # oldest -> latest, yearly
  "operating_cash_flow_cr": [70, 90, 100, 120],
  "total_debt_cr": 200.0,            # borrowings, latest
  "cash_cr": 50.0,                   # cash + liquid investments, latest
  "equity_cr": 900.0,                # net worth (share capital + reserves), latest
  "ebit_cr": 180.0,                  # operating profit before interest & tax, latest
  "interest_cr": 15.0,               # finance cost, latest
  "dividend_per_share": 12.0,        # ₹, latest full year
  "promoter_holding_pct": 55.0,
  "promoter_pledge_pct": 0.0,        # % of promoter shares pledged
  "promoter_change_4q_pp": -1.5,     # change over the LAST ~4 QUARTERS only, percentage points
  "ttm_net_profit_cr": 140.0,        # optional: last 4 quarters' profit (may be negative)
  "eps_shares_cr": 99.5,             # optional: weighted-average diluted shares for EPS
  "equity_prev_cr": 820.0,           # optional: previous year-end net worth (average-equity ROE)
  "debt_prev_cr": 230.0,             # optional: previous year-end borrowings (average capital employed ROCE)
  "years": ["FY23", "FY24", "FY25", "FY26"],  # optional: labels for revenue_cr / net_profit_cr
  "ocf_years": ["FY25", "FY26"],     # optional: labels for operating_cash_flow_cr (and capex_cr)
  "capex_cr": [60, 140]              # optional: capital expenditure, positive numbers, same years as OCF
}

Output: ratios, a band for each ("comfortable" | "watch" | "concern" | "info"),
a band_note key explaining the rule of thumb, and red_flags. The output is
language-neutral; the mentor explains it in the user's language.

Bands are broad rules of thumb for teaching, not verdicts. They differ by sector,
and the script says so when sector_type changes the interpretation.
"""
import json
import math
import sys


def cagr(series):
    """Compound annual growth rate (oldest -> latest). Undefined if ANY year is zero or negative:
    a loss in the middle makes a start-to-end growth rate misleading."""
    if not series or len(series) < 2:
        return None
    if any(x is None or x <= 0 for x in series):
        return None
    start, end, years = series[0], series[-1], len(series) - 1
    return (end / start) ** (1 / years) - 1


def pct(x):
    return None if x is None else round(x * 100, 1)


# Single source of truth for teaching bands. build_dashboard.py draws its range bars
# from the "zones"/"scale" attached to each ratio, so the bar and the flag can't disagree.
# name: (comfortable_boundary, watch_boundary, higher_is_better, scale_min, scale_max)
THRESHOLDS = {
    "growth": (0.10, 0.05, True, -10, 50),          # CAGR, as fraction; scale in %
    "roe": (0.15, 0.10, True, 0, 40),
    "roe_fin": (0.12, 0.08, True, 0, 30),           # banks / NBFCs / insurers
    "roce": (0.15, 0.10, True, 0, 40),
    "de": (0.5, 1.0, False, 0, 2),
    "icr": (5, 2, True, 0, 20),
    "cash_conv": (0.8, 0.5, True, 0, 1.5),
    "pe": (25, 50, False, 0, 120),
    "peg": (1.5, 2.5, False, 0, 4),
    "pb_fin": (2.5, 4, False, 0, 8),
    "payout": (0.7, 1.0, False, 0, 1.2),            # fraction; scale in %
    "pledge": (0.0, 10, False, 0, 50),
}
PCT_SCALE = {"growth", "roe", "roe_fin", "roce", "payout"}  # thresholds are fractions, values shown in %


def zones_for(name):
    c, w, hib, lo, hi = THRESHOLDS[name]
    k = 100 if name in PCT_SCALE else 1
    c, w = c * k, w * k
    if hib:
        z = [[w, "concern"], [c, "watch"], [None, "comfortable"]]
    else:
        z = [[c, "comfortable"], [w, "watch"], [None, "concern"]]
    return {"zones": z, "scale": [lo, hi]}


def banded(name, value, display_value, note, **extra):
    c, w, hib, _, _ = THRESHOLDS[name]
    # Band the number the reader actually sees, so "0.8" is never flagged as below 0.8.
    shown = display_value / 100 if name in PCT_SCALE else display_value
    out = {"value": display_value, "band": band(shown, c, w, hib), "band_note": note}
    out.update(zones_for(name))
    out.update(extra)
    return out


def band(value, comfortable, watch, higher_is_better=True):
    """Return a band given thresholds. comfortable/watch are boundary values."""
    if value is None:
        return None
    if higher_is_better:
        if value >= comfortable:
            return "comfortable"
        if value >= watch:
            return "watch"
        return "concern"
    if value <= comfortable:
        return "comfortable"
    if value <= watch:
        return "watch"
    return "concern"


def latest(series):
    return series[-1] if series else None


NUMERIC = ("price", "shares_outstanding_cr", "total_debt_cr", "cash_cr", "equity_cr", "ebit_cr",
           "interest_cr", "dividend_per_share", "promoter_holding_pct", "promoter_pledge_pct",
           "promoter_change_4q_pp", "ttm_net_profit_cr", "eps_shares_cr", "equity_prev_cr", "debt_prev_cr")
NON_NEGATIVE = ("total_debt_cr", "cash_cr", "interest_cr", "dividend_per_share", "debt_prev_cr")
PERCENT_0_100 = ("promoter_holding_pct", "promoter_pledge_pct")
SERIES = ("revenue_cr", "net_profit_cr", "operating_cash_flow_cr", "capex_cr")


class InputError(ValueError):
    pass


def validate_input(d):
    """Reject inputs that would produce confident nonsense. Returns a list of problems."""
    problems = []
    if "promoter_holding_change_pp" in d:
        problems.append("'promoter_holding_change_pp' was renamed to 'promoter_change_4q_pp' "
                        "(change over the last ~4 quarters, in percentage points). Do not put a multi-year change here.")
    def ok_num(x):
        return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)
    for k in NUMERIC:
        v = d.get(k)
        if v is not None and not ok_num(v):
            problems.append(f"'{k}' must be a finite number, got {type(v).__name__} {v!r}")
    for k in SERIES:
        v = d.get(k)
        if v is not None:
            if not isinstance(v, list) or not all(ok_num(x) for x in v):
                problems.append(f"'{k}' must be a list of finite numbers, oldest to latest")
    for k in NON_NEGATIVE:
        v = d.get(k)
        if ok_num(v) and v < 0:
            problems.append(f"'{k}' cannot be negative, got {v}")
    for k in PERCENT_0_100:
        v = d.get(k)
        if ok_num(v) and not 0 <= v <= 100:
            problems.append(f"'{k}' must be between 0 and 100, got {v}")
    v = d.get("promoter_change_4q_pp")
    if ok_num(v) and not -100 <= v <= 100:
        problems.append(f"'promoter_change_4q_pp' must be between -100 and 100, got {v}")
    cx = d.get("capex_cr")
    if isinstance(cx, list) and all(ok_num(x) for x in cx):
        if any(x < 0 for x in cx):
            problems.append("'capex_cr' is money spent on assets: enter it as positive numbers")
        if not isinstance(d.get("operating_cash_flow_cr"), list) or len(d["operating_cash_flow_cr"]) != len(cx):
            problems.append("'capex_cr' must cover the same years as 'operating_cash_flow_cr'")
    rev = d.get("revenue_cr")
    if isinstance(rev, list) and all(ok_num(x) for x in rev) and any(x < 0 for x in rev):
        problems.append("'revenue_cr' cannot contain negative values")
    for lab, ser in (("years", ("revenue_cr", "net_profit_cr")), ("ocf_years", ("operating_cash_flow_cr", "capex_cr"))):
        if lab in d:
            y = d[lab]
            if not (isinstance(y, list) and all(isinstance(x, str) and x.strip() for x in y)) or len(set(y)) != len(y):
                problems.append(f"'{lab}' must be a list of unique fiscal-year labels like \"FY25\"")
                continue
            for k in ser:
                if isinstance(d.get(k), list) and len(d[k]) != len(y):
                    problems.append(f"'{k}' has {len(d[k])} values but '{lab}' lists {len(y)} years")
    lens = {k: len(d[k]) for k in ("revenue_cr", "net_profit_cr") if isinstance(d.get(k), list)}
    if len(set(lens.values())) > 1:
        problems.append(f"'revenue_cr' and 'net_profit_cr' must cover the same years, got lengths {lens}")
    for k in ("price", "shares_outstanding_cr", "eps_shares_cr"):
        v = d.get(k)
        if isinstance(v, (int, float)) and v <= 0:
            problems.append(f"'{k}' must be greater than 0, got {v}")
    if d.get("sector_type", "general") not in ("general", "bank", "nbfc", "insurance", "cyclical"):
        problems.append(f"'sector_type' must be general/bank/nbfc/insurance/cyclical, got {d.get('sector_type')!r}")
    return problems


def compute(d):
    problems = validate_input(d)
    if problems:
        raise InputError("Invalid input:\n  - " + "\n  - ".join(problems))
    out = {"company": d.get("company"), "as_of": d.get("as_of"), "ratios": {}, "red_flags": [], "notes": [],
           "inputs": {k: d.get(k) for k in ("price", "shares_outstanding_cr", "eps_shares_cr", "ttm_net_profit_cr", "sector_type")}}
    r = out["ratios"]
    sector = d.get("sector_type", "general")
    financial = sector in ("bank", "nbfc", "insurance")

    price = d.get("price")
    shares = d.get("shares_outstanding_cr")
    revenue = d.get("revenue_cr") or []
    profit = d.get("net_profit_cr") or []
    ocf = d.get("operating_cash_flow_cr") or []
    debt = d.get("total_debt_cr")
    cash = d.get("cash_cr")
    equity = d.get("equity_cr")
    ebit = d.get("ebit_cr")
    interest = d.get("interest_cr")
    dps = d.get("dividend_per_share")

    # Market cap and per-share numbers
    if price is not None and shares:
        mcap = price * shares  # ₹ crore, since shares are in crore
        r["market_cap_cr"] = {"value": round(mcap, 1), "band": "info", "band_note": "market_cap_size"}
    else:
        mcap = None

    np_latest = latest(profit)
    eps_shares = d["eps_shares_cr"] if d.get("eps_shares_cr") is not None else shares  # validated > 0
    if d.get("eps_shares_cr"):
        out["notes"].append("eps_uses_weighted_diluted_shares")
    if np_latest is not None and eps_shares:
        eps = np_latest / eps_shares  # ₹ per share
        r["eps_rs"] = {"value": round(eps, 2), "band": "info", "band_note": "eps"}
        if price is not None:
            if eps > 0:
                pe = price / eps
                r["pe"] = banded("pe", pe, round(pe, 1), "pe_compare_with_sector_and_growth")
            else:
                r["pe"] = {"value": None, "band": "concern", "band_note": "pe_undefined_loss_making"}
                out["red_flags"].append("loss_making_latest_year")

    ttm = d.get("ttm_net_profit_cr")
    ttm_loss = ttm is not None and ttm <= 0
    if ttm is not None and price is not None and eps_shares:
        if ttm > 0:
            pe_t = price / (ttm / eps_shares)
            r["pe_ttm"] = banded("pe", pe_t, round(pe_t, 1), "pe_ttm_uses_last_4_quarters")
        else:
            r["pe_ttm"] = {"value": None, "band": "concern", "band_note": "pe_ttm_not_meaningful_loss_last_4_quarters"}
            out["red_flags"].append("loss_making_last_4_quarters")

    if equity and price is not None and shares:
        pb = mcap / equity
        if equity > 0:
            r["pb"] = (banded("pb_fin", pb, round(pb, 2), "pb_key_for_financials") if financial else
                       {"value": round(pb, 2), "band": "info", "band_note": "pb_secondary_for_non_financials"})

    # Growth
    rev_g = cagr(revenue)
    if rev_g is not None:
        r["revenue_cagr_pct"] = banded("growth", rev_g, pct(rev_g), "growth_vs_inflation", years=len(revenue) - 1)
    prof_g = cagr(profit)
    if prof_g is not None:
        r["profit_cagr_pct"] = banded("growth", prof_g, pct(prof_g), "growth_vs_inflation", years=len(profit) - 1)
    elif len(profit) >= 2:
        out["notes"].append("profit_cagr_undefined_due_to_loss_or_zero_year")
        if any(x <= 0 for x in profit[1:-1]):
            out["red_flags"].append("loss_in_an_intermediate_year")
    if rev_g is not None and prof_g is not None and rev_g > 0.05 and prof_g < 0:
        out["red_flags"].append("sales_growing_but_profit_falling")

    def yoy(series):
        if len(series) >= 2 and series[-2] and series[-2] > 0:
            return series[-1] / series[-2] - 1
        return None
    rev_y, prof_y = yoy(revenue), yoy(profit)
    if rev_y is not None:
        r["revenue_growth_latest_pct"] = {"value": pct(rev_y), "band": "info", "band_note": "latest_year_vs_previous"}
    if prof_y is not None:
        r["profit_growth_latest_pct"] = {"value": pct(prof_y), "band": "info", "band_note": "latest_year_vs_previous"}
    if rev_y is not None and prof_y is not None and rev_y > 0 and prof_y < 0 \
            and "sales_growing_but_profit_falling" not in out["red_flags"]:
        out["red_flags"].append("sales_up_but_profit_down_latest_year")
    if len(profit) >= 3 and profit[-1] < profit[-2] < profit[-3]:
        out["red_flags"].append("profit_fell_two_years_in_a_row")

    # PEG (only meaningful with positive growth)
    if "pe" in r and r["pe"]["value"] and prof_g and prof_g > 0 and not ttm_loss:
        peg = r["pe"]["value"] / (prof_g * 100)
        r["peg"] = banded("peg", peg, round(peg, 2), "peg_rough_guide_past_growth_not_future")

    # Profitability
    rev_latest = latest(revenue)
    if np_latest is not None and rev_latest:
        margin = np_latest / rev_latest
        r["net_margin_pct"] = {"value": pct(margin), "band": "info", "band_note": "margin_varies_by_industry"}
    if equity is not None and equity <= 0:
        out["red_flags"].append("negative_or_zero_net_worth")
        out["notes"].append("roe_de_pb_not_meaningful_with_negative_equity")
    eq_prev = d.get("equity_prev_cr")
    eq_for_roe = (equity + eq_prev) / 2 if (equity and eq_prev and eq_prev > 0) else equity
    if eq_for_roe is not equity:
        out["notes"].append("roe_uses_average_equity")
    if np_latest is not None and equity and equity > 0:
        roe = np_latest / eq_for_roe
        r["roe_pct"] = (banded("roe_fin", roe, pct(roe), "roe_financials_12_15_good") if financial else
                        banded("roe", roe, pct(roe), "roe_with_debt_check"))
    if ebit is not None and equity is not None and debt is not None and not financial:
        cap_employed = equity + debt
        eq_p, debt_p = d.get("equity_prev_cr"), d.get("debt_prev_cr")
        if eq_p is not None and debt_p is not None and eq_p + debt_p > 0:
            cap_employed = (cap_employed + eq_p + debt_p) / 2
            out["notes"].append("roce_uses_average_capital_employed")
        if cap_employed > 0:
            roce = ebit / cap_employed
            r["roce_pct"] = banded("roce", roce, pct(roce), "roce_core_quality")

    # Debt
    if not financial:
        if debt is not None and equity and equity > 0:
            de = debt / equity
            r["debt_to_equity"] = banded("de", de, round(de, 2), "debt_family_emi_analogy")
            if de > 2:
                out["red_flags"].append("very_high_debt")
        if debt is not None and cash is not None:
            r["net_debt_cr"] = {"value": round(debt - cash, 1), "band": "info",
                                "band_note": "net_cash_if_negative"}
        if ebit is not None and interest:
            icr = ebit / interest
            r["interest_coverage"] = banded("icr", icr, round(icr, 1), "interest_coverage_times")
            if icr < 1.5:
                out["red_flags"].append("struggling_to_pay_interest")
    else:
        out["notes"].append("financial_company_debt_ratios_not_applicable_use_npa_casa_capital_adequacy")

    # Cash quality: is profit turning into cash?
    if ocf and profit:
        years, ocf_years = d.get("years"), d.get("ocf_years")
        if years and ocf_years:
            common = [y for y in years if y in ocf_years]           # match by label, not by position
            pv = [profit[years.index(y)] for y in common]
            ov = [ocf[ocf_years.index(y)] for y in common]
            n = len(common)
            if n < max(len(ocf), len(profit)):
                out["notes"].append("cash_conversion_uses_only_years_present_in_both_series")
        else:
            n = min(len(ocf), len(profit))
            pv, ov = profit[-n:], ocf[-n:]
            out["notes"].append("cash_conversion_assumes_both_series_end_in_the_same_year")
        periods = common if (years and ocf_years) else None
        ocf_sum, np_sum = sum(ov), sum(pv)
        if np_sum > 0 and not financial:
            conv = ocf_sum / np_sum
            if n >= 2:
                r["cash_conversion"] = banded("cash_conv", conv, round(conv, 2), "profit_should_become_cash", years=n)
                if periods:
                    r["cash_conversion"]["periods"] = periods
            else:
                r["cash_conversion"] = {"value": round(conv, 2), "band": "info", "years": n,
                                        "band_note": "one_year_only_not_enough_for_a_signal"}
            if conv < 0.5 and n >= 2:
                out["red_flags"].append("profits_not_converting_to_cash")

    # Free cash flow = operating cash flow − capex (same years, so the same labels as ocf_years)
    capex = d.get("capex_cr") or []
    if capex and ocf and len(capex) == len(ocf):
        fcf = [o - c for o, c in zip(ocf, capex)]
        r["fcf_latest_cr"] = {"value": round(fcf[-1], 1), "band": "info", "band_note": "fcf_cash_left_after_investing"}
        if len(fcf) >= 2:
            r["fcf_total_cr"] = {"value": round(sum(fcf), 1), "years": len(fcf), "band": "info",
                                 "band_note": "fcf_total_over_period"}
            if d.get("ocf_years"):
                r["fcf_total_cr"]["periods"] = d["ocf_years"]
            if sum(fcf) < 0:
                out["red_flags"].append("free_cash_flow_negative_over_period")
        if sum(ocf) > 0:
            r["capex_to_ocf_pct"] = {"value": pct(sum(capex) / sum(ocf)), "band": "info",
                                     "band_note": "share_of_operating_cash_reinvested"}
        if mcap and mcap > 0:
            r["fcf_yield_pct"] = {"value": pct(fcf[-1] / mcap), "band": "info", "band_note": "fcf_yield_compare_fd"}

    # Dividend
    if dps is not None and price:
        dy = dps / price
        r["dividend_yield_pct"] = {"value": pct(dy), "band": "info", "band_note": "dividend_yield_compare_fd"}
        if np_latest and shares and np_latest > 0:
            payout = (dps * shares) / np_latest
            r["payout_ratio_pct"] = banded("payout", payout, pct(payout), "payout_over_100_unsustainable")

    # Ownership and governance
    pledge = d.get("promoter_pledge_pct")
    if pledge is not None:
        r["promoter_pledge_pct"] = banded("pledge", pledge, pledge, "pledge_risk_forced_selling")
        if pledge > 25:
            out["red_flags"].append("high_promoter_pledge")
    ph = d.get("promoter_holding_pct")
    if ph is not None:
        r["promoter_holding_pct"] = {"value": ph, "band": "info", "band_note": "promoter_holding_context"}
    chg = d.get("promoter_change_4q_pp")
    if chg is not None and chg <= -5:
        out["red_flags"].append("promoters_reducing_stake_sharply")

    # Unit sanity check: the commonest input error is shares not in crore
    pe_v = r.get("pe", {}).get("value")
    pb_v = r.get("pb", {}).get("value")
    if (pe_v and pe_v > 300) or (pb_v and pb_v > 60):
        out["notes"].append("check_units_shares_must_be_in_crore_and_money_in_crore")

    if sector == "cyclical":
        out["notes"].append("cyclical_low_pe_can_mean_peak_earnings")
    if financial:
        out["notes"].append("use_bank_nbfc_section_of_framework")
        out["notes"].append("sector_analysis_incomplete_npa_casa_nim_crar_not_computed")
    out["notes"].append("bands_are_teaching_rules_of_thumb_not_verdicts")
    return out


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    with open(sys.argv[1], encoding="utf-8") as f:
        data = json.load(f)
    try:
        result = compute(data)
    except InputError as e:
        print(e, file=sys.stderr)
        sys.exit(2)
    indent = 2 if "--pretty" in sys.argv else None
    print(json.dumps(result, ensure_ascii=False, indent=indent))


if __name__ == "__main__":
    main()
