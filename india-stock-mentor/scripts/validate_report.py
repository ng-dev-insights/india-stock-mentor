#!/usr/bin/env python3
"""
Validate a report's content.json against the ratios.py output before publishing.

Usage:
    python3 validate_report.py ratios.json content.json

Errors (exit 1) — the report must not be delivered until fixed:
  E1  scenarios.price, lesson.simulator.price and the ratios input price differ
  E2  scenarios.eps and lesson.simulator.eps differ (two baselines on one page)
  E3  that EPS doesn't match TTM profit ÷ shares (or annual EPS if no TTM)
  E4  scenarios.today_pe doesn't match the P/E implied by price ÷ EPS
  E5  a metric row asks for a ratio that ratios.json doesn't have
  E6  a market-cap chip disagrees with the computed market cap by > 1%
  E7  price_line doesn't show the price used in the calculations
  E8  price_line doesn't show the as_of date (day, month and year)
  E9  scenarios or a calculator are present although the last 4 quarters were loss-making
  E10 the calculator's eps_basis doesn't match the data (TTM when positive TTM profit exists, else annual)
Warnings (printed, exit 0):
  W2  a P/E metric's text doesn't mention its rounded value
"""
import json
import re
import sys
from datetime import date

# Month names a price_line may use, by month number. Add a language here before using it.
MONTHS = {
    1: ["jan", "january", "जानेवारी", "जनवरी"], 2: ["feb", "february", "फेब्रुवारी", "फ़रवरी", "फरवरी"],
    3: ["mar", "march", "मार्च"], 4: ["apr", "april", "एप्रिल", "अप्रैल"], 5: ["may", "मे", "मई"],
    6: ["jun", "june", "जून"], 7: ["jul", "july", "जुलै", "जुलाई"], 8: ["aug", "august", "ऑगस्ट", "अगस्त"],
    9: ["sep", "sept", "september", "सप्टेंबर", "सितंबर"], 10: ["oct", "october", "ऑक्टोबर", "अक्टूबर"],
    11: ["nov", "november", "नोव्हेंबर", "नवंबर"], 12: ["dec", "december", "डिसेंबर", "दिसंबर"],
}


def month_in(text, m):
    # Split on spaces and punctuation only: regex word classes break Devanagari words at vowel signs.
    tokens = [t for t in re.split(r"[\s·,.()/:;\-–—]+", text.lower()) if t]
    for name in MONTHS[m]:
        for t in tokens:
            if t == name or (len(name) > 2 and t.startswith(name)):   # allows suffixes like "नोव्हेंबरची"
                return True
    return False


NUM = re.compile(r"\d+(?:[.,]\d+)*")


def nums(text):
    return [float(m.replace(",", "")) for m in NUM.findall(text or "")]


def close(a, b, tol):
    return a is not None and b is not None and abs(a - b) <= tol * max(abs(a), abs(b), 1e-9)


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(2)
    R = json.load(open(sys.argv[1], encoding="utf-8"))
    C = json.load(open(sys.argv[2], encoding="utf-8"))
    ratios, inp = R.get("ratios", {}), R.get("inputs", {})
    errors, warns = [], []

    price = inp.get("price")
    shares = inp.get("eps_shares_cr") or inp.get("shares_outstanding_cr")  # same denominator as ratios.py
    ttm = inp.get("ttm_net_profit_cr")
    sc = C.get("scenarios") or {}
    sim = (C.get("lesson") or {}).get("simulator") or {}

    # E1 price
    prices = {"ratios": price, "scenarios": sc.get("price"), "simulator": sim.get("price")}
    given = {k: v for k, v in prices.items() if v is not None}
    if len(set(round(v, 2) for v in given.values())) > 1:
        errors.append(f"E1 price differs across the report: {given}")

    # E2 one EPS baseline
    if sc.get("eps") is not None and sim.get("eps") is not None and not close(sc["eps"], sim["eps"], 0.01):
        errors.append(f"E2 two EPS baselines on one page: scenarios {sc['eps']} vs calculator {sim['eps']}")

    # E3 EPS matches data
    base_eps = (ttm / shares) if (ttm and ttm > 0 and shares) else (ratios.get("eps_rs") or {}).get("value")
    for name, e in (("scenarios", sc.get("eps")), ("calculator", sim.get("eps"))):
        if e is not None and base_eps and not close(e, base_eps, 0.02):
            errors.append(f"E3 {name} EPS {e} doesn't match data ({base_eps:.2f} = {'TTM' if ttm else 'annual'} profit ÷ EPS shares)")
    if sim:
        expected = "ttm" if (ttm is not None and ttm > 0) else "annual"
        if sim.get("eps_basis") != expected:
            errors.append(f"E10 calculator says eps_basis={sim.get('eps_basis')!r} but the data calls for {expected!r}")
    if ttm is not None and ttm <= 0 and (sc or sim):
        errors.append("E9 last 4 quarters were loss-making: P/E-based scenarios and calculator are not meaningful; remove them")

    # E4 today's P/E
    if sc.get("today_pe") is not None and price and sc.get("eps"):
        implied = price / sc["eps"]
        if not close(sc["today_pe"], implied, 0.02):
            errors.append(f"E4 today_pe {sc['today_pe']} but price ÷ EPS = {implied:.1f}")

    # E5 metric rows exist
    for m in C.get("metrics", []):
        if m.get("key") not in ratios or ratios[m["key"]].get("value") is None:
            errors.append(f"E5 metric '{m.get('key')}' requested but not in ratios.json (row would silently vanish)")

    # E6 market cap chip
    mcap = (ratios.get("market_cap_cr") or {}).get("value")
    for chip in C.get("chips", []):
        if "cap" in chip.get("label", "").lower() and mcap:
            vals = nums(chip.get("value"))
            if vals and not close(vals[0], mcap, 0.01):
                errors.append(f"E6 market-cap chip says {vals[0]:,.0f} but computed {mcap:,.0f}")

    # E7/E8 header price and date
    pl = C.get("price_line", "")
    if price and round(price) not in [round(v) for v in nums(pl)]:
        errors.append(f"E7 price_line «{pl}» doesn't show the price used in calculations ({price:,.0f})")
    if R.get("as_of"):
        try:
            d = date.fromisoformat(R["as_of"])
            pn = [int(v) for v in nums(pl) if v == int(v)]
            if d.day not in pn or d.year not in pn or not month_in(pl, d.month):
                errors.append(f"E8 price_line «{pl}» doesn't show the as_of date {R['as_of']} (day, month, year)")
        except ValueError:
            errors.append(f"E8 as_of {R['as_of']!r} is not an ISO date (YYYY-MM-DD)")
    elif price:
        errors.append("E8 ratios.json has a price but no as_of date")

    # W2 P/E text mentions its value
    for m in C.get("metrics", []):
        if m.get("key") in ("pe", "pe_ttm") and m.get("key") in ratios:
            v = ratios[m["key"]].get("value")
            if v and round(v) not in [round(x) for x in nums(m.get("meaning"))]:
                warns.append(f"W2 {m['key']} text doesn't mention ~{round(v)}: «{m.get('meaning', '')[:80]}»")

    for w in warns:
        print("warning:", w)
    if errors:
        print(f"{len(errors)} error(s) — do not publish:")
        for e in errors:
            print(" -", e)
        sys.exit(1)
    print("Report numbers validated.")


if __name__ == "__main__":
    main()
