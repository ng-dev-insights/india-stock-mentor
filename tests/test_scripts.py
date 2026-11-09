"""Tests for the India Stock Mentor scripts.
Run from the repo root:  python -m unittest discover -s tests -v
Standard library only."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "india-stock-mentor", "scripts")
EXAMPLE = os.path.join(ROOT, "examples", "acutaas")
sys.path.insert(0, SCRIPTS)

from ratios import compute, cagr, InputError, THRESHOLDS, PCT_SCALE, banded  # noqa: E402
from build_dashboard import build, inr, ContentError      # noqa: E402


def load(name):
    with open(os.path.join(EXAMPLE, name), encoding="utf-8") as f:
        return json.load(f)


def run(script, *args):
    return subprocess.run([sys.executable, os.path.join(SCRIPTS, script), *args],
                          capture_output=True, text=True)


def zone_band(r):
    """Classify a value using the zones drawn on the bar (must match the flag)."""
    v = r["value"]
    hib = r["zones"][-1][1] == "comfortable"
    for upper, band in r["zones"]:
        if upper is None or (v < upper if hib else v <= upper):
            return band


class TestFormulas(unittest.TestCase):
    def test_cagr_known_values(self):
        self.assertAlmostEqual(cagr([100, 121]), 0.21, places=6)       # 1 year
        self.assertAlmostEqual(cagr([100, 110, 121]), 0.10, places=6)
        self.assertIsNone(cagr([100]))
        self.assertIsNone(cagr([-10, 20]))   # undefined across losses

    def test_acutaas_fixture(self):
        r = compute(load("input.json"))["ratios"]
        self.assertAlmostEqual(r["market_cap_cr"]["value"], 3786.60 * 8.4088, delta=0.5)
        self.assertEqual(r["pe"]["value"], 89.4)        # 3786.6 / (356.26 / 8.4088)
        self.assertEqual(r["pe_ttm"]["value"], 72.8)    # 3786.6 / (437.1 / 8.4088)
        self.assertEqual(r["roe_pct"]["value"], 21.4)   # 356.26 / 1668.4
        self.assertEqual(r["revenue_cagr_pct"]["value"], 26.7)
        self.assertEqual(r["cash_conversion"]["value"], 0.8)  # cumulative 410.51 / 514.97

    def test_cash_conversion_is_cumulative(self):
        r = compute({"net_profit_cr": [10, 100], "operating_cash_flow_cr": [0, 100]})["ratios"]
        self.assertEqual(r["cash_conversion"]["value"], round(100 / 110, 2))  # not mean(0, 1)


class TestSafety(unittest.TestCase):
    def test_negative_equity_never_looks_safe(self):
        out = compute({"price": 100, "shares_outstanding_cr": 1, "net_profit_cr": [10, -20],
                       "equity_cr": -50, "total_debt_cr": 200})
        self.assertNotIn("debt_to_equity", out["ratios"])
        self.assertNotIn("roe_pct", out["ratios"])
        self.assertIn("negative_or_zero_net_worth", out["red_flags"])

    def test_bad_inputs_rejected(self):
        for bad in ({"price": 0, "shares_outstanding_cr": 1}, {"price": "100", "shares_outstanding_cr": 1},
                    {"net_profit_cr": "10,20"}, {"promoter_holding_change_pp": -6}, {"sector_type": "tech"}):
            with self.assertRaises(InputError, msg=bad):
                compute(bad)

    def test_bank_roe_band_matches_note(self):
        r = compute({"sector_type": "bank", "net_profit_cr": [120], "equity_cr": 1000})["ratios"]
        self.assertEqual(r["roe_pct"]["band"], "comfortable")  # 12% is good for a bank
        self.assertNotIn("debt_to_equity", r)                   # not meaningful for lenders

    def test_bar_and_flag_always_agree(self):
        inputs = [load("input.json"),
                  {"price": 500, "shares_outstanding_cr": 2, "net_profit_cr": [50, 40, 55], "revenue_cr": [500, 520, 560],
                   "equity_cr": 400, "total_debt_cr": 380, "ebit_cr": 70, "interest_cr": 30, "dividend_per_share": 30,
                   "operating_cash_flow_cr": [20, 25, 30], "promoter_pledge_pct": 12}]
        for d in inputs:
            for key, r in compute(d)["ratios"].items():
                if "zones" in r:
                    self.assertEqual(zone_band(r), r["band"], f"{key}: bar {zone_band(r)} vs flag {r['band']}")

    def test_threshold_table_complete(self):
        for name, t in THRESHOLDS.items():
            self.assertEqual(len(t), 5, name)


class TestReport(unittest.TestCase):
    def test_indian_grouping(self):
        self.assertEqual(inr(148461), "1,48,461")
        self.assertEqual(inr(12345678), "1,23,45,678")
        self.assertEqual(inr(999), "999")
        self.assertEqual(inr(-72605), "-72,605")

    def test_html_is_escaped(self):
        html = build({"ratios": {}, "inputs": {}},
                     {"company": "<script>alert(1)</script>", "business": "<img src=x onerror=alert(1)>",
                      "quiz": {"q": "q", "options": ["<svg onload=alert(1)>", "b"], "answer": 1}})
        for raw in ("<script>alert", "<img src=x", "<svg onload"):
            self.assertNotIn(raw, html)

    def test_bad_content_rejected_with_message(self):
        for bad in ({"company": "X", "lesson": {"simulator": {"eps": 5}}},
                    {"company": "X", "history": {"years": ["a", "b"], "series": [{"name": "r", "values": [1]}]}},
                    {"company": "X", "quiz": {"q": "q", "options": ["a"], "answer": 3}},
                    {"company": ""}):
            with self.assertRaises(ContentError, msg=bad):
                build({"ratios": {}, "inputs": {}}, bad)

    def test_loss_years_drawn_below_zero(self):
        html = build({"ratios": {}, "inputs": {}},
                     {"company": "X", "history": {"years": ["FY1", "FY2"],
                                                  "series": [{"name": "Profit", "values": [-40, 60]}]}})
        self.assertIn('class="s0 neg"', html)
        self.assertIn('class="zero"', html)


class TestValidators(unittest.TestCase):
    def test_example_passes_all_checks(self):
        with tempfile.TemporaryDirectory() as t:
            rj = os.path.join(t, "ratios.json")
            with open(rj, "w") as f:
                f.write(run("ratios.py", os.path.join(EXAMPLE, "input.json")).stdout)
            for lang in ("en", "mr"):
                res = run("validate_report.py", rj, os.path.join(EXAMPLE, f"content_{lang}.json"))
                self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
                res = run("build_dashboard.py", rj, os.path.join(EXAMPLE, f"content_{lang}.json"),
                          os.path.join(t, f"r_{lang}.html"))
                self.assertEqual(res.returncode, 0, res.stderr)
        res = run("check_consistency.py", os.path.join(EXAMPLE, "content_en.json"),
                  os.path.join(EXAMPLE, "content_mr.json"))
        self.assertEqual(res.returncode, 0, res.stdout)

    def test_validator_catches_two_eps_baselines(self):
        c = load("content_en.json")
        c["lesson"]["simulator"]["eps"] = 42.37   # the bug a reviewer found in an early version
        with tempfile.TemporaryDirectory() as t:
            cj, rj = os.path.join(t, "c.json"), os.path.join(t, "r.json")
            with open(cj, "w") as f:
                json.dump(c, f)
            with open(rj, "w") as f:
                json.dump(compute(load("input.json")), f)
            res = run("validate_report.py", rj, cj)
        self.assertEqual(res.returncode, 1)
        self.assertIn("E2", res.stdout)

    def test_consistency_catches_changed_number(self):
        en, mr = load("content_en.json"), load("content_mr.json")
        mr["concerns"][0] = mr["concerns"][0].replace("89", "92")
        with tempfile.TemporaryDirectory() as t:
            a, b = os.path.join(t, "a.json"), os.path.join(t, "b.json")
            for path, data in ((a, en), (b, mr)):
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False)
            res = run("check_consistency.py", a, b)
        self.assertEqual(res.returncode, 1)
        self.assertIn("concerns[0]", res.stdout)


class TestReviewV2(unittest.TestCase):
    """One test per finding from the external code review (V2)."""

    def test_bar_and_flag_agree_for_every_threshold_and_value(self):
        # Sweeps each threshold across its scale, including values right at and next to boundaries.
        for name, (c, w, hib, lo, hi) in THRESHOLDS.items():
            k = 100 if name in PCT_SCALE else 1
            pts = {lo, hi, c * k, w * k, 0.1, 0.5, 1}
            for b in (c * k, w * k):
                pts |= {b - 0.01, b + 0.01}
            pts |= {lo + (hi - lo) * i / 40 for i in range(41)}
            for shown in sorted(pts):
                raw = shown / k
                r = banded(name, raw, round(shown, 2), "test")
                self.assertEqual(zone_band(r), r["band"], f"{name} at {shown}: bar {zone_band(r)} vs flag {r['band']}")

    def test_issue2_non_finite_negative_and_out_of_range_rejected(self):
        bad = [{"price": float("nan"), "shares_outstanding_cr": 1}, {"price": float("inf"), "shares_outstanding_cr": 1},
               {"total_debt_cr": -10}, {"cash_cr": -2}, {"interest_cr": -1}, {"promoter_holding_pct": 150},
               {"promoter_pledge_pct": 120}, {"promoter_pledge_pct": -1}, {"revenue_cr": [100, -5]},
               {"revenue_cr": [1, 2, 3], "net_profit_cr": [1, 2]}, {"net_profit_cr": [1, float("nan")]}]
        for d in bad:
            with self.assertRaises(InputError, msg=d):
                compute(d)
        # legitimate negatives stay allowed
        compute({"net_profit_cr": [10, -20], "equity_cr": -5, "operating_cash_flow_cr": [-3, 4], "ebit_cr": -2})

    def test_issue3_small_pledge_bar_matches_flag(self):
        for p in (0, 0.1, 0.5, 1, 10, 10.1):
            r = compute({"promoter_pledge_pct": p})["ratios"]["promoter_pledge_pct"]
            self.assertEqual(zone_band(r), r["band"], p)

    def test_issue4_recent_profit_decline_flagged(self):
        out = compute({"revenue_cr": [100, 120, 150, 180], "net_profit_cr": [10, 20, 18, 17]})
        self.assertGreater(out["ratios"]["profit_cagr_pct"]["value"], 15)   # headline CAGR still looks fine
        self.assertIn("profit_fell_two_years_in_a_row", out["red_flags"])
        self.assertIn("sales_up_but_profit_down_latest_year", out["red_flags"])
        self.assertEqual(out["ratios"]["profit_growth_latest_pct"]["value"], -5.6)

    def test_issue5_ttm_loss_is_explicit(self):
        out = compute({"price": 100, "shares_outstanding_cr": 1, "net_profit_cr": [4, 5], "ttm_net_profit_cr": -3})
        self.assertIsNone(out["ratios"]["pe_ttm"]["value"])
        self.assertEqual(out["ratios"]["pe_ttm"]["band_note"], "pe_ttm_not_meaningful_loss_last_4_quarters")
        self.assertIn("loss_making_last_4_quarters", out["red_flags"])
        self.assertNotIn("peg", out["ratios"])                              # no PEG when the latest year is a loss

    def test_issue6_invalid_scenarios_rejected_not_crashing(self):
        base = {"price": 100, "eps": 10, "years": 5, "cases": [{"name": "B", "growth": 20, "pe": 20}]}
        for patch in ({"years": 0}, {"years": 2.5}, {"cases": [{"name": "B", "growth": -100, "pe": 20}]},
                      {"cases": [{"name": "B", "growth": 10, "pe": 0}]}, {"cases": []},
                      {"target_return": float("nan")}, {"need_at_pe": [0]}):
            sc = dict(base, **patch)
            with self.assertRaises(ContentError, msg=patch):
                build({"ratios": {}, "inputs": {}}, {"company": "X", "scenarios": sc})

    def test_wrong_header_price_or_date_is_a_hard_error(self):
        c = load("content_en.json")
        with tempfile.TemporaryDirectory() as t:
            rj = os.path.join(t, "r.json")
            with open(rj, "w") as f:
                json.dump(compute(load("input.json")), f)
            for line, code in (("₹3,999 · price as of 6 Nov 2026", "E7"), ("₹3,787 · price as of 1 Oct 2026", "E8")):
                c["price_line"] = line
                cj = os.path.join(t, "c.json")
                with open(cj, "w", encoding="utf-8") as f:
                    json.dump(c, f, ensure_ascii=False)
                res = run("validate_report.py", rj, cj)
                self.assertEqual(res.returncode, 1, line)
                self.assertIn(code, res.stdout)

    def test_publish_gate_blocks_inconsistent_reports(self):
        mr = load("content_mr.json")
        mr["lesson"]["simulator"]["eps"] = 42.37
        with tempfile.TemporaryDirectory() as t:
            bad = os.path.join(t, "content_mr.json")
            with open(bad, "w", encoding="utf-8") as f:
                json.dump(mr, f, ensure_ascii=False)
            out = os.path.join(t, "out")
            res = run("publish_report.py", os.path.join(EXAMPLE, "input.json"),
                      os.path.join(EXAMPLE, "content_en.json"), bad, "--out", out)
            self.assertEqual(res.returncode, 1)
            self.assertFalse(os.path.exists(out), "nothing may be published when a check fails")
            ok = run("publish_report.py", os.path.join(EXAMPLE, "input.json"),
                     os.path.join(EXAMPLE, "content_en.json"), os.path.join(EXAMPLE, "content_mr.json"), "--out", out)
            self.assertEqual(ok.returncode, 0, ok.stderr)
            self.assertTrue(os.path.exists(os.path.join(out, "report_mr.html")))

    def test_optional_methodology_fields(self):
        a = compute({"price": 100, "shares_outstanding_cr": 10, "net_profit_cr": [50], "eps_shares_cr": 9})
        self.assertAlmostEqual(a["ratios"]["eps_rs"]["value"], round(50 / 9, 2))
        self.assertEqual(a["ratios"]["market_cap_cr"]["value"], 1000)     # market cap still uses current shares
        b = compute({"net_profit_cr": [100], "equity_cr": 600, "equity_prev_cr": 400})
        self.assertEqual(b["ratios"]["roe_pct"]["value"], 20.0)            # 100 / average(600, 400)
        c1 = compute({"net_profit_cr": [10], "operating_cash_flow_cr": [2]})
        self.assertEqual(c1["ratios"]["cash_conversion"]["band"], "info")  # one year: no health signal
        self.assertNotIn("profits_not_converting_to_cash", c1["red_flags"])


class TestReviewV21(unittest.TestCase):
    """Findings from the V2 review."""

    def _validate(self, R, C):
        with tempfile.TemporaryDirectory() as t:
            rj, cj = os.path.join(t, "r.json"), os.path.join(t, "c.json")
            with open(rj, "w") as f:
                json.dump(R, f)
            with open(cj, "w", encoding="utf-8") as f:
                json.dump(C, f, ensure_ascii=False)
            return run("validate_report.py", rj, cj)

    def test_p0_1_validator_uses_weighted_eps_denominator(self):
        R = compute({"price": 100, "shares_outstanding_cr": 10, "net_profit_cr": [40, 50], "ttm_net_profit_cr": 54,
                     "eps_shares_cr": 9, "as_of": "2026-11-06"})
        R["as_of"] = "2026-11-06"
        C = {"company": "X", "price_line": "₹100 · 6 Nov 2026",
             "scenarios": {"price": 100, "eps": 6.0, "years": 5, "cases": [{"name": "B", "growth": 10, "pe": 20}]}}
        self.assertEqual(self._validate(R, C).returncode, 0)          # 54 / 9 = 6.0 is correct
        C["scenarios"]["eps"] = 5.4                                    # 54 / 10 uses the wrong denominator
        self.assertIn("E3", self._validate(R, C).stdout)

    def test_p0_2_zero_eps_shares_rejected(self):
        for v in (0, -1):
            with self.assertRaises(InputError):
                compute({"price": 100, "shares_outstanding_cr": 10, "eps_shares_cr": v})

    def test_p0_3_schema_catches_typos_and_types(self):
        bad = [{"company": "X", "positives": "one string"}, {"company": "X", "scenario": {}},
               {"company": "X", "metrics": [{"label": "no key"}]}, {"company": "X", "chips": [{"label": "a"}]},
               {"company": "X", "events": {"items": [{"title": "t", "tag": "great"}]}},
               {"company": "X", "quiz": {"q": "q", "options": ["only one"], "answer": 0}},
               {"company": "X", "labels": {"sc_need_part": "{growth} at {pe}"}},
               {"company": "X", "labels": {"scenarioz": "typo"}}, ["not", "an", "object"]]
        for c in bad:
            with self.assertRaises(ContentError, msg=c):
                build({"ratios": {}, "inputs": {}}, c)
        for name in ("content_en.json", "content_mr.json"):        # real examples still pass
            build({"ratios": {}, "inputs": {}}, load(name))

    def test_p0_4_simulator_values_must_fit_the_sliders(self):
        from build_dashboard import SIM_LIMITS
        for k in ("growth", "years", "future_pe"):
            lo, hi, _ = SIM_LIMITS[k]
            for v in (lo - 1, hi + 1):
                sim = {"price": 100, "eps": 5, "eps_basis": "ttm", k: v}
                with self.assertRaises(ContentError, msg=(k, v)):
                    build({"ratios": {}, "inputs": {}}, {"company": "X", "lesson": {"title": "t", "body": [], "simulator": sim}})
        html = build({"ratios": {}, "inputs": {}}, {"company": "X", "lesson": {"title": "t", "body": [],
                      "simulator": {"price": 100, "eps": 5, "eps_basis": "ttm", "growth": 60, "years": 10, "future_pe": 150}}})
        self.assertIn(f'min="{SIM_LIMITS["growth"][0]}" max="{SIM_LIMITS["growth"][1]}"', html)

    def test_p1_month_is_checked_in_english_and_marathi(self):
        R = compute(load("input.json"))
        for line, ok in (("₹3,787 · price as of 6 Nov 2026", True), ("₹3,787 · price as of 6 Dec 2026", False),
                         ("₹3,787 · 6 नोव्हेंबर 2026 ची किंमत", True), ("₹3,787 · 6 ऑक्टोबर 2026 ची किंमत", False)):
            C = load("content_en.json")
            C["price_line"] = line
            res = self._validate(R, C)
            self.assertEqual(res.returncode == 0, ok, line + res.stdout)

    def test_ttm_loss_report_with_scenarios_rejected(self):
        R = compute({"price": 100, "shares_outstanding_cr": 1, "net_profit_cr": [4, 5], "ttm_net_profit_cr": -3,
                     "as_of": "2026-11-06"})
        R["as_of"] = "2026-11-06"
        C = {"company": "X", "price_line": "₹100 · 6 Nov 2026",
             "scenarios": {"price": 100, "eps": 5.0, "years": 5, "cases": [{"name": "B", "growth": 10, "pe": 20}]}}
        self.assertIn("E9", self._validate(R, C).stdout)

    def test_p2_duplicate_languages_and_atomic_publish(self):
        with tempfile.TemporaryDirectory() as t:
            out = os.path.join(t, "out")
            ok = run("publish_report.py", os.path.join(EXAMPLE, "input.json"),
                     os.path.join(EXAMPLE, "content_en.json"), os.path.join(EXAMPLE, "content_mr.json"), "--out", out)
            self.assertEqual(ok.returncode, 0, ok.stderr)
            before = open(os.path.join(out, "report_en.html"), encoding="utf-8").read()
            dup = run("publish_report.py", os.path.join(EXAMPLE, "input.json"),
                      os.path.join(EXAMPLE, "content_en.json"), os.path.join(EXAMPLE, "content_en.json"), "--out", out)
            self.assertEqual(dup.returncode, 1)
            self.assertIn("same lang", dup.stderr)
            self.assertEqual(open(os.path.join(out, "report_en.html"), encoding="utf-8").read(), before)  # untouched
            self.assertFalse([f for f in os.listdir(t) if f.startswith(".stage-") or f.endswith(".previous")])


class TestReviewV22(unittest.TestCase):
    """Findings from the V2.1 review."""

    def test_a_malformed_nested_content_rejected_not_crashing(self):
        bad = [{"lesson": {"title": "t", "body": [], "simulator": "oops"}},
               {"scenarios": {"price": 1, "eps": 1, "cases": {"bad": 1}}}, {"scenarios": "oops"},
               {"history": {"years": "FY1", "series": "x"}}, {"history": {"years": ["a"], "series": [{"name": "r", "values": "1"}]}},
               {"scenarios": {"price": 1, "eps": 1, "cases": [{"name": 5, "growth": 1, "pe": 2}]}},
               {"scenarios": {"price": 1, "eps": 1, "cases": [], "need_at_pe": 40}}, {"metrics": "x"}, {"events": []},
               {"quiz": "q"}, {"labels": ["x"]}]
        for extra in bad:
            with self.assertRaises(ContentError, msg=extra):
                build({"ratios": {}, "inputs": {}}, dict({"company": "X"}, **extra))

    def test_b_unsafe_language_codes_rejected(self):
        for lang in ("../../escaped", "en/../x", "EN", "e", "en_IN", "mr IN", "", 5):
            with self.assertRaises(ContentError, msg=lang):
                build({"ratios": {}, "inputs": {}}, {"company": "X", "lang": lang})
        for lang in ("en", "mr", "hi", "mr-IN", "en-IN"):
            build({"ratios": {}, "inputs": {}}, {"company": "X", "lang": lang})
        c = load("content_en.json")
        c["lang"] = "../../escaped"
        with tempfile.TemporaryDirectory() as t:
            cj = os.path.join(t, "c.json")
            with open(cj, "w", encoding="utf-8") as f:
                json.dump(c, f, ensure_ascii=False)
            res = run("publish_report.py", os.path.join(EXAMPLE, "input.json"), cj, "--out", os.path.join(t, "out"))
            self.assertEqual(res.returncode, 1)
            self.assertIn("invalid language code", res.stderr)
            self.assertNotIn("Traceback", res.stderr)

    def test_c_failed_swap_restores_original_output(self):
        from publish_report import atomic_swap
        with tempfile.TemporaryDirectory() as t:
            out, stage = os.path.join(t, "out"), os.path.join(t, "stage")
            os.makedirs(out)
            os.makedirs(stage)
            with open(os.path.join(out, "report_en.html"), "w") as f:
                f.write("ORIGINAL")
            calls = []

            def flaky(src, dst):
                calls.append((src, dst))
                if len(calls) == 2:                      # backup succeeds, swap-in fails
                    raise OSError("simulated failure")
                os.replace(src, dst)
            with self.assertRaises(OSError):
                atomic_swap(stage, out, _replace=flaky)
            self.assertEqual(open(os.path.join(out, "report_en.html")).read(), "ORIGINAL")
            self.assertFalse(os.path.exists(out + ".previous"))
            # and the normal path still works
            atomic_swap(stage, out)
            self.assertFalse(os.path.exists(os.path.join(out, "report_en.html")))

    def test_d_signs_are_compared(self):
        from check_consistency import numbers
        self.assertNotEqual(numbers("−27%"), numbers("+27%"))
        self.assertEqual(numbers("−27%"), numbers("-27%"))          # Unicode minus == hyphen
        self.assertEqual(numbers("(27)"), [-27.0])                  # accounting style
        self.assertEqual(numbers("38–40%"), [38.0, 40.0])           # range, not negative
        self.assertEqual(numbers("FY2025-26"), [26.0, 2025.0])      # year range, not negative
        en, mr = load("content_en.json"), load("content_mr.json")
        mr["scenarios"]["intro"] = mr["scenarios"]["intro"].replace("₹3,787", "−₹3,787")
        with tempfile.TemporaryDirectory() as t:
            a, b = os.path.join(t, "a.json"), os.path.join(t, "b.json")
            for path, data in ((a, en), (b, mr)):
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False)
            res = run("check_consistency.py", a, b)
        self.assertEqual(res.returncode, 1)
        self.assertIn("scenarios/intro", res.stdout)

    def test_roce_average_capital_employed(self):
        r = compute({"ebit_cr": 30, "equity_cr": 120, "total_debt_cr": 30, "equity_prev_cr": 80, "debt_prev_cr": 20})
        self.assertEqual(r["ratios"]["roce_pct"]["value"], 24.0)    # 30 / average(150, 100)
        self.assertIn("roce_uses_average_capital_employed", r["notes"])

    def test_cash_conversion_aligned_by_fiscal_year(self):
        base = {"net_profit_cr": [10, 20, 40], "operating_cash_flow_cr": [8, 16]}
        positional = compute(base)["ratios"]["cash_conversion"]["value"]          # pairs 8,16 with 20,40
        labelled = compute(dict(base, years=["FY24", "FY25", "FY26"], ocf_years=["FY24", "FY25"]))
        self.assertEqual(positional, round(24 / 60, 2))
        self.assertEqual(labelled["ratios"]["cash_conversion"]["value"], round(24 / 30, 2))  # pairs by year
        self.assertIn("cash_conversion_uses_only_years_present_in_both_series", labelled["notes"])
        for bad in ({"net_profit_cr": [1, 2], "years": ["FY25"]}, {"years": ["FY25", "FY25"]},
                    {"operating_cash_flow_cr": [1], "ocf_years": ["FY25", "FY26"]}):
            with self.assertRaises(InputError, msg=bad):
                compute(bad)


class TestV03Features(unittest.TestCase):
    def test_free_cash_flow(self):
        r = compute({"price": 100, "shares_outstanding_cr": 10, "net_profit_cr": [40, 50],
                     "operating_cash_flow_cr": [50, 60], "capex_cr": [70, 30], "ocf_years": ["FY25", "FY26"]})
        m = r["ratios"]
        self.assertEqual(m["fcf_latest_cr"]["value"], 30)          # 60 - 30
        self.assertEqual(m["fcf_total_cr"]["value"], 10)           # (50-70) + (60-30)
        self.assertEqual(m["fcf_total_cr"]["periods"], ["FY25", "FY26"])
        self.assertEqual(m["capex_to_ocf_pct"]["value"], 90.9)     # 100 / 110
        self.assertEqual(m["fcf_yield_pct"]["value"], 3.0)         # 30 / market cap 1000
        burn = compute({"operating_cash_flow_cr": [50, 60], "capex_cr": [90, 80]})
        self.assertIn("free_cash_flow_negative_over_period", burn["red_flags"])

    def test_capex_input_rules(self):
        for bad in ({"operating_cash_flow_cr": [50, 60], "capex_cr": [-10, 20]},
                    {"operating_cash_flow_cr": [50, 60], "capex_cr": [10]},
                    {"capex_cr": [10, 20]},
                    {"operating_cash_flow_cr": [50, 60], "capex_cr": [10, 20], "ocf_years": ["FY26"]}):
            with self.assertRaises(InputError, msg=bad):
                compute(bad)

    def test_crore_metrics_display_with_rupee_and_indian_grouping(self):
        R = compute({"operating_cash_flow_cr": [150000, 160000], "capex_cr": [10000, 12345]})
        html = build(R, {"company": "X", "metrics": [{"key": "fcf_latest_cr", "label": "FCF"}]})
        self.assertIn("₹1,47,655 cr", html)

    def test_chart_has_screen_reader_table(self):
        html = build({"ratios": {}, "inputs": {}}, {"company": "X", "history": {"title": "Growth", "unit": "₹ cr",
                     "years": ["FY25", "FY26"], "series": [{"name": "Revenue", "values": [100, 150]}]}})
        self.assertIn('aria-describedby="hist-data"', html)
        self.assertIn('<table class="sr-only" id="hist-data">', html)
        self.assertIn("<td>150</td>", html)

    def test_print_stylesheet_forces_light_paper(self):
        from build_dashboard import CSS
        self.assertIn("@media print", CSS)
        block = CSS[CSS.index("@media print"):]
        self.assertIn("--paper:#FFFFFF", block)
        self.assertIn(":root:root:root", block)                       # beats the dark-mode selectors
        self.assertIn("break-inside:avoid", block)

    def test_dry_run_touches_nothing(self):
        with tempfile.TemporaryDirectory() as t:
            out = os.path.join(t, "out")
            res = run("publish_report.py", os.path.join(EXAMPLE, "input.json"), os.path.join(EXAMPLE, "content_en.json"),
                      os.path.join(EXAMPLE, "content_mr.json"), "--out", out, "--dry-run")
            self.assertEqual(res.returncode, 0, res.stderr)
            self.assertIn("Dry run passed: 2 language(s)", res.stdout)
            self.assertFalse(os.path.exists(out))
            self.assertEqual(os.listdir(t), [])


class TestReviewV22b(unittest.TestCase):
    def test_cagr_undefined_across_intermediate_loss_or_zero(self):
        self.assertIsNone(cagr([100, -50, 400]))
        self.assertIsNone(cagr([100, 0, 400]))
        out = compute({"net_profit_cr": [100, -50, 400]})
        self.assertNotIn("profit_cagr_pct", out["ratios"])             # no "100%, Comfortable"
        self.assertIn("profit_cagr_undefined_due_to_loss_or_zero_year", out["notes"])
        self.assertIn("loss_in_an_intermediate_year", out["red_flags"])

    def test_eps_basis_label_follows_the_data(self):
        def sim(**kw):
            return {"company": "X", "lesson": {"title": "t", "body": [], "simulator": dict({"price": 100, "eps": 5}, **kw)}}
        R = {"ratios": {}, "inputs": {}}
        self.assertIn("(last 4 quarters)", build(R, sim(eps_basis="ttm")))
        self.assertIn("(FY26 annual)", build(R, sim(eps_basis="annual", eps_period="FY26")))
        for bad in ({}, {"eps_basis": "annual"}, {"eps_basis": "quarterly"}):
            with self.assertRaises(ContentError, msg=bad):
                build(R, sim(**bad))
        # validator: label must match what the data supports
        R2 = compute({"price": 100, "shares_outstanding_cr": 1, "net_profit_cr": [4, 5], "ttm_net_profit_cr": 6})
        R2["as_of"] = "2026-11-06"
        C = {"company": "X", "price_line": "₹100 · 6 Nov 2026",
             "lesson": {"title": "t", "body": [], "simulator": {"price": 100, "eps": 6.0, "eps_basis": "annual", "eps_period": "FY26"}}}
        with tempfile.TemporaryDirectory() as t:
            rj, cj = os.path.join(t, "r.json"), os.path.join(t, "c.json")
            with open(rj, "w") as f:
                json.dump(R2, f)
            with open(cj, "w", encoding="utf-8") as f:
                json.dump(C, f, ensure_ascii=False)
            res = run("validate_report.py", rj, cj)
        self.assertIn("E10", res.stdout)


if __name__ == "__main__":
    unittest.main()
