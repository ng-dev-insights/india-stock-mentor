#!/usr/bin/env python3
"""
Build a one-page "stock health report" (styled like a pathology lab report)
from ratios.py output plus content written in the learner's language.

Usage:
    python3 build_dashboard.py ratios.json content.json out.html

ratios.json : the JSON printed by ratios.py
content.json: everything a reader sees, already written in the learner's
              language. The script never invents text; every label can be
              overridden, so the report works in any language and script.

content.json fields (all optional except company):
{
  "lang": "mr",                       # BCP-47 code for <html lang>
  "company": "Acutaas Chemicals Ltd",
  "symbol": "NSE: ACUTAAS",
  "price_line": "₹3,898 · 2 Nov 2026",
  "basis_line": "Consolidated, FY26 (year ended Mar 2026)",
  "business": "Two or three plain sentences about the business.",
  "metrics": [                        # rows to show, in order
     {"key": "pe", "label": "P/E ratio", "native": "किंमत-उत्पन्न गुणोत्तर",
      "meaning": "One line in the learner's language."}
  ],
  "chips": [{"label": "Market cap", "value": "₹32,778 cr"}],
  "history": {"title": "...", "years": ["FY22",...], "series": [
       {"name": "Revenue", "values": [520, ...]},
       {"name": "Profit",  "values": [72, ...]}], "unit": "₹ cr"},
  "positives": ["..."], "concerns": ["..."], "questions": ["..."],
  "lesson": {"title": "...", "body": ["paragraph", "..."],
             "simulator": {"price": 3898, "eps": 42.37,
                           "growth": 25, "years": 5, "future_pe": 30}},
  "events": {"window": "Last 90 days (...)", "correction": "optional",
             "items": [{"date": "27 Oct 2026", "tag": "good|bad|neutral",
                        "importance": "high|medium|low", "title": "...",
                        "why": "...", "not_conclude": "...", "source": "..."}]},
  "scenarios": {"price": 3786.6, "eps": 52.2, "eps_basis": "ttm", "years": 5, "target_return": 12,
                "need_at_pe": [40, 30], "intro": "...",
                "cases": [{"name": "Bear", "growth": 12, "pe": 30}, ...]},
  "quiz": {"q": "...", "a": "..."},
  "sources": ["..."],
  "disclaimer": "...",
  "labels": { ...override any key in DEFAULT_LABELS... }
}
"""
import html
import json
import math
import re
import sys

DEFAULT_LABELS = {
    "report_title": "Stock health report",
    "results": "Test results",
    "col_test": "Test",
    "col_result": "Result",
    "col_range": "Where it falls",
    "flag_comfortable": "Comfortable",
    "flag_watch": "Watch",
    "flag_concern": "Concern",
    "range_note": "Ranges are general rules of thumb for learning. Normal levels differ by sector.",
    "history": "How the business has grown",
    "positives": "What’s going well",
    "concerns": "What to watch out for",
    "questions": "Questions a smart investor asks next",
    "lesson": "Today’s lesson",
    "sim_title": "Try it yourself",
    "sim_growth": "Profit growth per year",
    "sim_years": "Years",
    "sim_pe": "What investors then pay per ₹1 of profit (P/E)",
    "sim_start_ttm": "Starting point: EPS ₹{eps} (last 4 quarters) at a share price of ₹{price}",
    "sim_start_annual": "Starting point: EPS ₹{eps} ({period} annual) at a share price of ₹{price}",
    "sim_future_eps": "Profit per share then",
    "sim_future_price": "Share price then",
    "sim_change": "Change from today’s price",
    "sim_per_year": "per year",
    "quiz": "Quick check",
    "quiz_show": "Show answer",
    "sources": "Sources",
    "business": "The business in brief",
    "events": "What changed recently",
    "tag_good": "Good sign",
    "tag_bad": "Concern",
    "tag_neutral": "Neutral",
    "imp_high": "High importance",
    "imp_medium": "Medium importance",
    "imp_low": "Low importance",
    "ev_why": "Why it matters",
    "ev_not": "What not to conclude",
    "ev_correction": "Correction to an earlier view",
    "kind_business": "Business",
    "kind_market": "Market reaction",
    "conf_filing": "Official filing",
    "conf_company": "Company statement",
    "conf_news": "News report (unconfirmed)",
    "quiz_right": "Correct.",
    "quiz_wrong": "Not quite.",
    "scenarios": "What has to go right?",
    "sc_how": "How this works: a share’s future price = the company’s profit per share then × how much investors pay for each ₹1 of that profit (the P/E). We don’t know either number, so here are three possible futures.",
    "sc_case": "If…",
    "sc_growth": "Profit grows every year by",
    "sc_pe": "Investors then pay, per ₹1 of profit",
    "sc_lakh": "₹1 lakh today becomes (in {n} yrs)",
    "sc_return": "Works out to, per year",
    "sc_need_title": "The key question",
    "sc_today": "Today investors pay about ₹{pe} for every ₹1 of yearly profit.",
    "sc_need": "To earn about {r}% a year (roughly what a Nifty index fund has averaged over long periods), profit must grow every year for {n} years by {parts}.",
    "sc_need_part": "about {g} if investors then pay ₹{pe} per ₹1 of profit",
    "sc_or": ", or ",
    "sc_note": "Growth rates and P/Es are illustrative assumptions, not forecasts.",
}

# Display units only. Zones and scales come from ratios.py (THRESHOLDS), attached to
# each ratio as "zones"/"scale", so the bar and the flag always use the same rule.
UNITS = {"revenue_cagr_pct": "%", "profit_cagr_pct": "%", "roe_pct": "%", "roce_pct": "%",
         "debt_to_equity": "×", "interest_coverage": "×", "cash_conversion": "×",
         "promoter_pledge_pct": "%", "payout_ratio_pct": "%", "net_margin_pct": "%",
         "dividend_yield_pct": "%", "promoter_holding_pct": "%", "capex_to_ocf_pct": "%", "fcf_yield_pct": "%",
         "revenue_growth_latest_pct": "%", "profit_growth_latest_pct": "%"}

ICON = {"comfortable": "●", "watch": "▲", "concern": "■"}


def esc(s):
    return html.escape(str(s), quote=True)


def fmt(v, unit):
    if v is None:
        return "–"
    if isinstance(v, float) and abs(v) >= 100:
        v = round(v)
    elif isinstance(v, float):
        v = round(v, 2 if abs(v) < 10 else 1)
    return f"{v:,}{unit}" if unit != "×" else f"{v}×"


def range_bar(r):
    value, (lo, hi), zones = r["value"], r["scale"], r["zones"]
    span = hi - lo
    segs, start = [], lo
    for upper, band in zones:
        end = hi if upper is None else min(upper, hi)
        w = max(0.0, (end - start) / span * 100)
        segs.append(f'<span class="seg seg-{band}" style="width:{w:.2f}%"></span>')
        start = max(start, end)
    clamped = min(max(value, lo), hi)
    pos = (clamped - lo) / span * 100
    over = ' over' if value > hi else (' under' if value < lo else '')
    return (f'<div class="bar" aria-hidden="true">{"".join(segs)}'
            f'<span class="marker{over}" style="left:{pos:.2f}%"></span></div>')


def metric_rows(ratios, metrics, L):
    rows = []
    for m in metrics:
        key = m["key"]
        r = ratios.get(key)
        if not r or r.get("value") is None:
            continue
        band = r.get("band") if r.get("band") in ICON else None
        unit = UNITS.get(key, "")
        flag = (f'<span class="flag flag-{band}">{ICON[band]} {esc(L["flag_" + band])}</span>'
                if band else "")
        bar = range_bar(r) if r.get("zones") and r.get("scale") else ""
        native = f'<span class="native">{esc(m["native"])}</span>' if m.get("native") else ""
        shown = f"₹{inr(r['value'])} cr" if key.endswith("_cr") else fmt(r["value"], unit)
        rows.append(f"""
      <div class="row row-{band or 'info'}">
        <div class="test"><span class="test-name">{esc(m.get('label', key))}</span>{native}</div>
        <div class="result"><span class="num">{esc(shown)}</span>{flag}</div>
        <div class="range">{bar}</div>
        <p class="meaning">{esc(m.get('meaning', ''))}</p>
      </div>""")
    return "".join(rows)


def history_svg(h):
    years, series = h.get("years", []), h.get("series", [])
    if not years or not series:
        return ""
    W, H, pad_l, pad_b, pad_t = 640, 240, 8, 28, 22
    n, k = len(years), len(series)
    allv = [v for s_ in series for v in s_["values"]]
    vmax, vmin = max(max(allv), 0), min(min(allv), 0)
    rng = (vmax - vmin) or 1
    plot_h = H - pad_b - pad_t
    zero_y = pad_t + plot_h * (vmax / rng)
    group_w = (W - pad_l * 2) / n
    bar_w = min(34, group_w / (k + 1))
    parts = [f'<line class="zero" x1="{pad_l}" x2="{W - pad_l}" y1="{zero_y:.1f}" y2="{zero_y:.1f}"/>'] if vmin < 0 else []
    for i, y in enumerate(years):
        gx = pad_l + i * group_w + (group_w - bar_w * k) / 2
        for j, s_ in enumerate(series):
            v = s_["values"][i]
            bh = plot_h * abs(v) / rng
            x = gx + j * bar_w
            top = zero_y - bh if v >= 0 else zero_y
            label_y = top - 5 if v >= 0 else top + bh + 13
            parts.append(f'<rect class="s{j}{" neg" if v < 0 else ""}" x="{x:.1f}" y="{top:.1f}" width="{bar_w - 4:.1f}" '
                         f'height="{max(bh, 0.5):.1f}" rx="2"><title>{esc(s_["name"])} {esc(y)}: {v:,}</title></rect>')
            parts.append(f'<text class="v" x="{x + (bar_w - 4) / 2:.1f}" y="{label_y:.1f}">{inr(v)}</text>')
        parts.append(f'<text class="yr" x="{gx + bar_w * k / 2:.1f}" y="{H - 8}">{esc(y)}</text>')
    legend = "".join(f'<span class="lg"><i class="s{j}"></i>{esc(s_["name"])}</span>' for j, s_ in enumerate(series))
    unit = f'<span class="unit">{esc(h.get("unit", ""))}</span>' if h.get("unit") else ""
    head = "".join(f'<th scope="col">{esc(y)}</th>' for y in years)
    body = "".join(f'<tr><th scope="row">{esc(s_["name"])}</th>' + "".join(f"<td>{inr(v)}</td>" for v in s_["values"]) + "</tr>"
                   for s_ in series)
    table = (f'<table class="sr-only" id="hist-data"><caption>{esc(h.get("title", ""))} ({esc(h.get("unit", ""))})</caption>'
             f'<thead><tr><td></td>{head}</tr></thead><tbody>{body}</tbody></table>')
    return (f'<div class="legend">{legend}{unit}</div>'
            f'<div class="chart-wrap"><svg viewBox="0 0 {W} {H}" role="img" aria-describedby="hist-data" '
            f'aria-label="{esc(h.get("title", ""))}">{"".join(parts)}</svg></div>{table}')


def items(lst, cls):
    if not lst:
        return ""
    return f'<ul class="{cls}">' + "".join(f"<li>{esc(x)}</li>" for x in lst) + "</ul>"


def simulator(sim, L):
    if not sim:
        return ""
    data = json.dumps({k: sim[k] for k in ("price", "eps") if k in sim})
    G, Y, P = SIM_LIMITS["growth"], SIM_LIMITS["years"], SIM_LIMITS["future_pe"]
    if sim.get("eps_basis") == "annual":
        start_line = L["sim_start_annual"].format(eps=f"{sim['eps']:.0f}", price=inr(sim["price"]), period=sim["eps_period"])
    else:
        start_line = L["sim_start_ttm"].format(eps=f"{sim['eps']:.0f}", price=inr(sim["price"]))
    return f"""
    <div class="sim" data-sim='{esc(data)}'>
      <h3>{esc(L['sim_title'])}</h3>
      <p class="sim-start">{esc(start_line)}</p>
      <label>{esc(L['sim_growth'])} <output id="og">{sim.get('growth', 20)}%</output>
        <input type="range" id="ig" min="{G[0]}" max="{G[1]}" step="{G[2]}" value="{sim.get('growth', 20)}"></label>
      <label>{esc(L['sim_years'])} <output id="oy">{sim.get('years', 5)}</output>
        <input type="range" id="iy" min="{Y[0]}" max="{Y[1]}" step="{Y[2]}" value="{sim.get('years', 5)}"></label>
      <label>{esc(L['sim_pe'])} <output id="op">{sim.get('future_pe', 30)}</output>
        <input type="range" id="ip" min="{P[0]}" max="{P[1]}" step="{P[2]}" value="{sim.get('future_pe', 30)}"></label>
      <dl class="sim-out">
        <div><dt>{esc(L['sim_future_eps'])}</dt><dd id="reps">–</dd></div>
        <div><dt>{esc(L['sim_future_price'])}</dt><dd id="rprice">–</dd></div>
        <div><dt>{esc(L['sim_change'])}</dt><dd id="rchg">–</dd></div>
      </dl>
    </div>"""


def inr(x):
    """Indian digit grouping: 148461 -> 1,48,461"""
    s = f"{round(x):d}"
    neg = s.startswith("-")
    s = s.lstrip("-")
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        s = ",".join(parts) + "," + tail
    return ("-" if neg else "") + s


# Calculator slider ranges. Validation and the HTML both read these, so a value the
# content asks for can always be shown exactly.
SIM_LIMITS = {"growth": (-20, 60, 1), "years": (1, 10, 1), "future_pe": (5, 150, 1)}

TAG_ICON = {"good": "●", "bad": "■", "neutral": "◆"}


def events_section(ev, L):
    if not ev or not ev.get("items"):
        return ""
    out = []
    for e in ev["items"]:
        tag = e.get("tag", "neutral") if e.get("tag") in TAG_ICON else "neutral"
        imp = e.get("importance", "low") if e.get("importance") in ("high", "medium", "low") else "low"
        meta = ""
        if e.get("kind") in ("business", "market"):
            meta += f'<span class="ev-meta">{esc(L["kind_" + e["kind"]])}</span>'
        if e.get("confidence") in ("filing", "company", "news"):
            meta += f'<span class="ev-meta conf-{e["confidence"]}">{esc(L["conf_" + e["confidence"]])}</span>'
        out.append(f"""
      <li class="ev ev-{tag}">
        <div class="ev-head"><span class="ev-date">{esc(e.get('date', ''))}</span>
          <span class="ev-tag tag-{tag}">{TAG_ICON[tag]} {esc(L['tag_' + tag])}</span>
          <span class="ev-imp imp-{imp}">{esc(L['imp_' + imp])}</span>{meta}</div>
        <p class="ev-title">{esc(e.get('title', ''))}</p>
        <p class="ev-line"><b>{esc(L['ev_why'])}:</b> {esc(e.get('why', ''))}</p>
        <p class="ev-line ev-not"><b>{esc(L['ev_not'])}:</b> {esc(e.get('not_conclude', ''))}</p>
        <p class="ev-src">{esc(e.get('source', ''))}</p>
      </li>""")
    corr = (f'<p class="correction"><b>{esc(L["ev_correction"])}:</b> {esc(ev["correction"])}</p>'
            if ev.get("correction") else "")
    win = f'<p class="note">{esc(ev.get("window", ""))}</p>' if ev.get("window") else ""
    return f'<section><h2>{esc(L["events"])}</h2>{win}{corr}<ul class="events">{"".join(out)}</ul></section>'


def scenario_section(sc, L):
    if not sc or not sc.get("cases"):
        return ""
    price, eps, n = sc["price"], sc["eps"], sc.get("years", 5)
    rows = []
    for c in sc["cases"]:
        g, pe = c["growth"] / 100, c["pe"]
        future = eps * (1 + g) ** n * pe
        lakh = 100000 * future / price
        ann = (future / price) ** (1 / n) - 1
        cls = "neg" if lakh < 100000 else "pos"
        desc = f'<span class="sc-desc">{esc(c["desc"])}</span>' if c.get("desc") else ""
        rows.append(f"<tr><th scope='row'><span class='sc-name'>{esc(c['name'])}</span>{desc}</th>"
                    f"<td data-l='{esc(L['sc_growth'])}'>{c['growth']}%</td>"
                    f"<td data-l='{esc(L['sc_pe'])}'>₹{pe}</td>"
                    f"<td class='{cls} big' data-l='{esc(L['sc_lakh'].format(n=n))}'>₹{inr(lakh)}</td>"
                    f"<td class='{cls}' data-l='{esc(L['sc_return'])}'>{ann:+.1%}</td></tr>")
    needs = []
    r = sc.get("target_return")
    if r and sc.get("need_at_pe"):
        parts = []
        for pe in sc["need_at_pe"]:
            g = (price * (1 + r / 100) ** n / pe / eps) ** (1 / n) - 1
            parts.append(L["sc_need_part"].format(g=f"{g:.0%}", pe=pe))
        needs.append(f"<p>{esc(L['sc_need'].format(r=r, n=n, parts=L['sc_or'].join(parts)))}</p>")
    if sc.get("today_pe"):
        needs.insert(0, f"<p>{esc(L['sc_today'].format(pe=round(sc['today_pe'])))}</p>")
    head = (f"<tr><th scope='col'>{esc(L['sc_case'])}</th><th scope='col'>{esc(L['sc_growth'])}</th>"
            f"<th scope='col'>{esc(L['sc_pe'])}</th><th scope='col'>{esc(L['sc_lakh'].format(n=n))}</th>"
            f"<th scope='col'>{esc(L['sc_return'])}</th></tr>")
    intro = f"<p>{esc(sc['intro'])}</p>" if sc.get("intro") else ""
    need_html = (f'<div class="need-box"><h3>{esc(L["sc_need_title"])}</h3>{"".join(needs)}</div>'
                 if needs else "")
    return (f'<section><h2>{esc(L["scenarios"])}</h2>{intro}<p class="how">{esc(L["sc_how"])}</p>'
            f'<div class="tbl-wrap"><table class="sc"><thead>{head}</thead><tbody>{"".join(rows)}</tbody></table></div>'
            f'{need_html}<p class="note">{esc(L["sc_note"])}</p></section>')


CSS = """
:root{--paper:#F5F8F8;--sheet:#FFFFFF;--ink:#1B2A31;--muted:#5B6B72;--rule:#D6DFE1;--lab:#0E6E6B;
--ok:#2E8B57;--warn:#B7791F;--bad:#B83A2E;--ok-bg:#E3F2EA;--warn-bg:#FBF0DC;--bad-bg:#F8E3E0;
--s0:#0E6E6B;--s1:#E0A43A;color-scheme:light;box-sizing:border-box;
padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--paper:#0F1719;--sheet:#172226;--ink:#E4ECEE;
--muted:#9AABB1;--rule:#2B3A3F;--lab:#4FB8B2;--ok:#5CC08A;--warn:#E3B160;--bad:#EE7D70;--ok-bg:#183326;
--warn-bg:#3A2E16;--bad-bg:#3D1E1B;--s0:#4FB8B2;--s1:#E3B160;color-scheme:dark}}
:root[data-theme="dark"]{--paper:#0F1719;--sheet:#172226;--ink:#E4ECEE;--muted:#9AABB1;--rule:#2B3A3F;--lab:#4FB8B2;
--ok:#5CC08A;--warn:#E3B160;--bad:#EE7D70;--ok-bg:#183326;--warn-bg:#3A2E16;--bad-bg:#3D1E1B;--s0:#4FB8B2;--s1:#E3B160;color-scheme:dark}
*,*::before,*::after{box-sizing:inherit}
html{scroll-padding-top:env(safe-area-inset-top,0px)}
body{margin:0;background:var(--paper);color:var(--ink);font-family:"Mukta","Noto Sans","Noto Sans Devanagari",system-ui,sans-serif;
font-size:17px;line-height:1.6;-webkit-text-size-adjust:100%}
.sheet{max-width:760px;margin:0 auto;background:var(--sheet);min-height:100vh;border-left:1px solid var(--rule);border-right:1px solid var(--rule)}
header.lab{border-top:6px solid var(--lab);padding:22px 22px 16px;border-bottom:2px solid var(--ink)}
.lab-top{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;color:var(--muted);font-size:15px}
h1{font-size:30px;line-height:1.2;margin:10px 0 2px;font-weight:700}
.sym{color:var(--muted);font-size:16px}
.meta{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:4px 18px;margin-top:12px;font-size:15px}
.meta b{font-weight:600}
section{padding:18px 22px;border-bottom:1px solid var(--rule)}
h2{font-size:21px;margin:0 0 10px;font-weight:700}
h3{font-size:18px;margin:0 0 8px}
.chips{display:flex;flex-wrap:wrap;gap:8px;margin-top:10px}
.chip{border:1px solid var(--rule);border-radius:6px;padding:4px 10px;font-size:15px}
.chip span{color:var(--muted);margin-right:6px}
.rows{border-top:1px solid var(--ink)}
.row{display:grid;grid-template-columns:1.25fr .9fr 1.4fr;gap:4px 14px;padding:12px 0;border-bottom:1px dashed var(--rule);align-items:center}
.row-concern .num{color:var(--bad)}
.test-name{font-weight:600;display:block}
.native{display:block;color:var(--muted);font-size:14px;line-height:1.3}
.num{font-size:22px;font-weight:700;font-variant-numeric:tabular-nums;display:block;line-height:1.2}
.flag{font-size:13px;font-weight:600;padding:1px 8px;border-radius:999px;display:inline-block;margin-top:2px}
.flag-comfortable{color:var(--ok);background:var(--ok-bg)}.flag-watch{color:var(--warn);background:var(--warn-bg)}
.flag-concern{color:var(--bad);background:var(--bad-bg)}
.bar{position:relative;display:flex;height:12px;border-radius:6px;overflow:visible}
.seg{height:100%;display:block}.seg:first-child{border-radius:6px 0 0 6px}.seg:last-of-type{border-radius:0 6px 6px 0}
.seg-comfortable{background:var(--ok-bg);box-shadow:inset 0 0 0 1px var(--ok)}
.seg-watch{background:var(--warn-bg);box-shadow:inset 0 0 0 1px var(--warn)}
.seg-concern{background:var(--bad-bg);box-shadow:inset 0 0 0 1px var(--bad)}
.marker{position:absolute;top:-5px;width:4px;height:22px;margin-left:-2px;background:var(--ink);border-radius:2px}
.marker.over::after{content:"▶";position:absolute;left:6px;top:1px;font-size:12px;color:var(--ink)}
.meaning{grid-column:1/-1;margin:2px 0 0;color:var(--muted);font-size:15.5px}
.note{font-size:14px;color:var(--muted);margin:10px 0 0}
.legend{display:flex;gap:16px;flex-wrap:wrap;font-size:15px;margin-bottom:6px}
.lg i{display:inline-block;width:12px;height:12px;border-radius:2px;margin-right:6px;vertical-align:-1px}
.unit{color:var(--muted);margin-left:auto}
.chart-wrap{overflow-x:auto}
svg{width:100%;min-width:420px;height:auto;display:block}
svg .s0,.lg .s0{fill:var(--s0);background:var(--s0)}svg .s1,.lg .s1{fill:var(--s1);background:var(--s1)}
svg text{fill:var(--muted);font-size:13px;text-anchor:middle;font-family:inherit}
svg text.v{fill:var(--ink);font-size:12px}
svg rect.neg{fill:var(--bad)}svg line.zero{stroke:var(--muted);stroke-width:1}
.two{display:grid;grid-template-columns:1fr 1fr;gap:18px}
ul{margin:0;padding-left:20px}li{margin:4px 0}
ul.good li::marker{color:var(--ok);content:"● "}ul.bad li::marker{color:var(--bad);content:"■ "}
ol{margin:0;padding-left:22px}
.lesson{border-left:4px solid var(--lab)}
.lesson p{margin:0 0 10px;max-width:65ch}
.sim{margin-top:14px;border:1px solid var(--rule);border-radius:8px;padding:14px}
.sim-start{margin:0 0 6px;font-size:15px;color:var(--muted)}
.sim label{display:block;margin:8px 0;font-size:15.5px}
.sim output{float:right;font-weight:700;font-variant-numeric:tabular-nums}
.sim input[type=range]{width:100%;accent-color:var(--lab);margin-top:4px}
.sim-out{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:12px 0 0}
.sim-out div{background:var(--paper);border-radius:6px;padding:8px 10px}
.sim-out dt{font-size:13.5px;color:var(--muted);line-height:1.3}
.sim-out dd{margin:2px 0 0;font-size:20px;font-weight:700;font-variant-numeric:tabular-nums}
details{margin-top:6px}summary{cursor:pointer;color:var(--lab);font-weight:600}
summary:focus-visible,input:focus-visible{outline:2px solid var(--lab);outline-offset:3px}
footer{padding:16px 22px 28px;font-size:14px;color:var(--muted)}
footer ul{padding-left:18px}.disc{margin-top:12px;padding:10px 12px;border:1px solid var(--rule);border-radius:6px;color:var(--ink)}
.events{list-style:none;padding:0;margin:0}
.ev{border-left:4px solid var(--rule);padding:8px 0 8px 14px;margin:0 0 12px}
.ev-good{border-color:var(--ok)}.ev-bad{border-color:var(--bad)}.ev-neutral{border-color:var(--muted)}
.ev-head{display:flex;flex-wrap:wrap;gap:6px 10px;align-items:center;font-size:14px}
.ev-date{font-weight:600}
.ev-tag{font-weight:600;padding:0 8px;border-radius:999px}
.tag-good{color:var(--ok);background:var(--ok-bg)}.tag-bad{color:var(--bad);background:var(--bad-bg)}
.tag-neutral{color:var(--muted);background:var(--paper)}
.ev-imp{color:var(--muted)}.imp-high{color:var(--ink);font-weight:600}
.ev-title{margin:4px 0 2px;font-weight:600;font-size:17px}
.ev-line{margin:2px 0;font-size:15.5px;max-width:68ch}.ev-not{color:var(--muted)}
.ev-src{margin:2px 0 0;font-size:13.5px;color:var(--muted)}
.ev-meta{color:var(--muted);border:1px solid var(--rule);border-radius:4px;padding:0 6px;font-size:13px}
.conf-news{border-style:dashed}
.qopts{display:grid;gap:8px;margin:8px 0}
.qopt{font:inherit;text-align:left;padding:10px 12px;border:1px solid var(--rule);border-radius:8px;background:var(--sheet);color:var(--ink);cursor:pointer}
.qopt:hover{border-color:var(--lab)}.qopt:focus-visible{outline:2px solid var(--lab);outline-offset:2px}
.qopt.right{border-color:var(--ok);background:var(--ok-bg)}.qopt.wrong{border-color:var(--bad);background:var(--bad-bg)}
.qres{margin:6px 0 0;max-width:68ch}
.correction{background:var(--warn-bg);border-radius:6px;padding:8px 12px;font-size:15.5px}
.tbl-wrap{overflow-x:auto}
table.sc{border-collapse:collapse;width:100%;min-width:480px;font-variant-numeric:tabular-nums;font-size:15.5px}
.sc th,.sc td{padding:8px 10px;border-bottom:1px solid var(--rule);text-align:right}
.sc th[scope=row],.sc thead th:first-child{text-align:left}
.sc thead th{font-size:14px;color:var(--muted);font-weight:600;border-bottom:2px solid var(--ink)}
.sc .neg{color:var(--bad);font-weight:600}.sc .pos{color:var(--ok);font-weight:600}
.needs{margin:0;padding-left:20px}
.need-box{margin-top:14px;border:1px solid var(--lab);border-radius:8px;padding:12px 14px}
.need-box h3{margin:0 0 6px}.need-box p{margin:0 0 6px;max-width:68ch}
.how{background:var(--paper);border-radius:6px;padding:10px 12px;font-size:15.5px;max-width:68ch}
.sc-name{display:block;font-weight:700}.sc-desc{display:block;font-weight:400;font-size:14px;color:var(--muted);line-height:1.35}
.sc thead th{vertical-align:bottom;line-height:1.3}
@media (max-width:620px){body{font-size:16px}h1{font-size:25px}
.row{grid-template-columns:1fr auto}.range{grid-column:1/-1}.result{text-align:right}
.two{grid-template-columns:1fr}.sim-out{grid-template-columns:1fr 1fr}.sim-out div:last-child{grid-column:1/-1}}
@media (max-width:620px){
table.sc{min-width:0}.sc thead{display:none}
.sc tr{display:block;border:1px solid var(--rule);border-radius:8px;padding:10px 12px;margin:0 0 10px}
.sc th[scope=row]{display:block;padding:0 0 6px;border:0}
.sc td{display:flex;justify-content:space-between;gap:12px;padding:3px 0;border:0;text-align:right}
.sc td::before{content:attr(data-l);color:var(--muted);text-align:left;font-weight:400}
.sc td.big{font-size:19px;align-items:baseline}.sc td.big::before{font-size:15.5px}}
.sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap;border:0}
@page{margin:14mm 12mm}
@media print{
:root:root:root{--paper:#FFFFFF;--sheet:#FFFFFF;--ink:#111111;--muted:#4A5257;--rule:#C9D1D3;--lab:#0E6E6B;
--ok:#2E7D4F;--warn:#9A6614;--bad:#A3332A;--ok-bg:#E3F2EA;--warn-bg:#FBF0DC;--bad-bg:#F8E3E0;--s0:#0E6E6B;--s1:#D4962E;
color-scheme:light;padding:0}
*{-webkit-print-color-adjust:exact;print-color-adjust:exact;box-shadow:none!important}
body{background:#fff;font-size:11.5pt}
.sheet{max-width:none;border:0;min-height:0}
section,header.lab,footer{padding-left:0;padding-right:0}
.chart-wrap,.tbl-wrap{overflow:visible}
svg,table.sc,.cmp,.entry{min-width:0!important}
.row,.ev,.sc tr,.need-box,.sim,.kpi,.chip,.qopt,.disc,.correction,.callout,figure,table{break-inside:avoid}
h2,h3,.legend{break-after:avoid}
.chart-wrap{break-before:avoid;break-inside:avoid}
section:has(> .chart-wrap){break-inside:avoid}
.sim input[type=range],.calc input[type=range],.calc select{display:none}
.quiz .qres{display:none}
a{color:inherit;text-decoration:none}
}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
"""

JS = """
(function(){var q=document.querySelector('.quiz');if(!q)return;var ans=+q.getAttribute('data-answer');
var res=q.querySelector('.qres'),v=q.querySelector('.qverdict');
q.querySelectorAll('.qopt').forEach(function(b){b.addEventListener('click',function(){
q.querySelectorAll('.qopt').forEach(function(x){x.classList.remove('right','wrong')});
var ok=+b.getAttribute('data-i')===ans;b.classList.add(ok?'right':'wrong');
if(!ok)q.querySelector('.qopt[data-i="'+ans+'"]').classList.add('right');
v.textContent=q.getAttribute(ok?'data-right':'data-wrong');res.hidden=false;});});})();
(function(){var box=document.querySelector('.sim');if(!box)return;
var d=JSON.parse(box.getAttribute('data-sim'));var g=document.getElementById('ig'),y=document.getElementById('iy'),p=document.getElementById('ip');
var nf=new Intl.NumberFormat('en-IN',{maximumFractionDigits:0});
var perYear=box.getAttribute('data-peryear')||'';
function run(){var gr=+g.value/100,yr=+y.value,pe=+p.value;
document.getElementById('og').textContent=g.value+'%';document.getElementById('oy').textContent=yr;document.getElementById('op').textContent=pe;
var eps=d.eps*Math.pow(1+gr,yr),price=eps*pe,chg=price/d.price-1,cagr=Math.pow(price/d.price,1/yr)-1;
document.getElementById('reps').textContent='₹'+nf.format(eps);document.getElementById('rprice').textContent='₹'+nf.format(price);
document.getElementById('rchg').textContent=(chg>=0?'+':'')+Math.round(chg*100)+'% ('+(cagr>=0?'+':'')+(cagr*100).toFixed(1)+'% '+perYear+')';}
[g,y,p].forEach(function(el){el.addEventListener('input',run)});run();})();
"""


class ContentError(ValueError):
    pass


def _num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


KNOWN_KEYS = {"lang", "company", "symbol", "price_line", "basis_line", "business", "metrics", "chips",
              "history", "events", "positives", "concerns", "questions", "scenarios", "lesson", "quiz",
              "sources", "disclaimer", "labels"}
TEMPLATED = {"sc_lakh": {"n": 5}, "sc_today": {"pe": 30}, "sc_need_part": {"g": "10%", "pe": 30},
             "sc_need": {"r": 12, "n": 5, "parts": "x"}, "sim_start_ttm": {"eps": "52", "price": "3,787"},
             "sim_start_annual": {"eps": "42", "price": "3,787", "period": "FY26"}}


LANG_RE = re.compile(r"^[a-z]{2,3}(-[A-Za-z0-9]{2,8})*$")   # BCP-47 style: en, mr, hi, mr-IN, en-IN


def _schema(c):
    """Types and shapes. Catches typos and wrong types before they become silent gaps or crashes."""
    p = []
    S = lambda x: isinstance(x, str)
    D = lambda x: isinstance(x, dict)
    L_ = lambda x: isinstance(x, list)
    if "lang" in c and not (S(c["lang"]) and LANG_RE.match(c["lang"])):
        p.append(f"'lang' must be a language code like en, mr, hi or mr-IN, got {c.get('lang')!r}")
    for k in ("scenarios", "lesson", "history", "events", "quiz", "labels"):
        if k in c and not D(c[k]):
            p.append(f"'{k}' must be an object")
    for k in ("metrics", "chips"):
        if k in c and not L_(c[k]):
            p.append(f"'{k}' must be a list")
    if p:
        return p
    sc = c.get("scenarios")
    if sc is not None:
        if "cases" in sc and not (L_(sc["cases"]) and all(D(x) for x in sc["cases"])):
            p.append("scenarios.cases must be a list of objects")
        if "need_at_pe" in sc and not L_(sc["need_at_pe"]):
            p.append("scenarios.need_at_pe must be a list")
        for i, cs in enumerate(sc.get("cases", []) if L_(sc.get("cases", [])) else []):
            if D(cs) and "name" in cs and not S(cs["name"]):
                p.append(f"scenarios.cases[{i}].name must be text")
    les = c.get("lesson")
    if les is not None and "simulator" in les and not D(les["simulator"]):
        p.append("lesson.simulator must be an object")
    h = c.get("history")
    if h is not None:
        if not (L_(h.get("years", [])) and all(S(y) for y in h.get("years", []))):
            p.append("history.years must be a list of text labels")
        ser = h.get("series", [])
        if not (L_(ser) and all(D(x) and S(x.get("name")) and L_(x.get("values")) for x in ser)):
            p.append("history.series must be a list of {name, values[]} objects")
    for k in set(c) - KNOWN_KEYS:
        p.append(f"unknown top-level key '{k}' (typo?)")
    for k in ("lang", "company", "symbol", "price_line", "basis_line", "business", "disclaimer"):
        if k in c and not S(c[k]):
            p.append(f"'{k}' must be text")
    for k in ("positives", "concerns", "questions", "sources"):
        if k in c and not (isinstance(c[k], list) and all(S(x) for x in c[k])):
            p.append(f"'{k}' must be a list of text items")
    for i, m in enumerate(c.get("metrics", []) if isinstance(c.get("metrics", []), list) else [None]):
        if not isinstance(m, dict) or not S(m.get("key")) or any(k in m and not S(m[k]) for k in ("label", "native", "meaning")):
            p.append(f"metrics[{i}] needs a text 'key' and optional text label/native/meaning")
    for i, ch in enumerate(c.get("chips", []) if isinstance(c.get("chips", []), list) else [None]):
        if not (isinstance(ch, dict) and S(ch.get("label")) and S(ch.get("value"))):
            p.append(f"chips[{i}] needs text 'label' and 'value'")
    ev = c.get("events")
    if ev is not None:
        items = ev.get("items") if isinstance(ev, dict) else None
        if not isinstance(items, list):
            p.append("events must be an object with an 'items' list")
        else:
            for i, e in enumerate(items):
                if not (isinstance(e, dict) and S(e.get("title"))):
                    p.append(f"events.items[{i}] needs a text 'title'")
                    continue
                for k, allowed in (("tag", TAG_ICON), ("importance", ("high", "medium", "low")),
                                   ("kind", ("business", "market")), ("confidence", ("filing", "company", "news"))):
                    if k in e and e[k] not in allowed:
                        p.append(f"events.items[{i}].{k} must be one of {sorted(allowed)}, got {e[k]!r}")
    les = c.get("lesson")
    if les is not None and not (isinstance(les, dict) and isinstance(les.get("body", []), list)
                                and all(S(x) for x in les.get("body", []))):
        p.append("lesson must have a text 'title' and a 'body' list of paragraphs")
    q = c.get("quiz")
    if q is not None:
        if not (isinstance(q, dict) and S(q.get("q"))):
            p.append("quiz needs a text 'q'")
        elif "options" in q and not (isinstance(q["options"], list) and len(q["options"]) >= 2 and all(S(o) for o in q["options"])):
            p.append("quiz.options must be a list of at least 2 text options")
        elif "options" not in q and not S(q.get("a")):
            p.append("quiz needs either 'options' + 'answer' or a text 'a'")
    labels = c.get("labels", {})
    if not (isinstance(labels, dict) and all(S(k) and S(v) for k, v in labels.items())):
        p.append("labels must map text keys to text values")
    else:
        for k in set(labels) - set(DEFAULT_LABELS):
            p.append(f"unknown label '{k}' (typo?)")
        for k, args in TEMPLATED.items():
            if k in labels:
                try:
                    labels[k].format(**args)
                except (KeyError, IndexError, ValueError) as e:
                    p.append(f"label '{k}' has an invalid placeholder ({e}); allowed: {sorted(args)}")
    return p


def validate_content(c):
    if not isinstance(c, dict):
        return ["content.json must be a JSON object"]
    p = _schema(c)
    if p:
        return p
    if not isinstance(c.get("company"), str) or not c["company"].strip():
        p.append("'company' is required")
    sim = (c.get("lesson") or {}).get("simulator")
    if sim is not None:
        for k in ("price", "eps"):
            if not _num(sim.get(k)) or sim.get(k) <= 0:
                p.append(f"lesson.simulator.{k} must be a finite number > 0")
        if sim.get("eps_basis") not in ("ttm", "annual"):
            p.append("lesson.simulator.eps_basis must be \"ttm\" or \"annual\" (it decides the starting-point label)")
        elif sim["eps_basis"] == "annual" and not (isinstance(sim.get("eps_period"), str) and sim["eps_period"].strip()):
            p.append("lesson.simulator.eps_period (e.g. \"FY26\") is required when eps_basis is \"annual\"")
        for k, default in (("growth", 20), ("years", 5), ("future_pe", 30)):
            lo, hi, _ = SIM_LIMITS[k]
            v = sim.get(k, default)
            if not (_num(v) and lo <= v <= hi) or (k == "years" and not isinstance(v, int)):
                p.append(f"lesson.simulator.{k} must be {'a whole number ' if k == 'years' else ''}between {lo} and {hi} (the slider's range), got {v!r}")
    sc = c.get("scenarios")
    if sc is not None:
        for k in ("price", "eps"):
            if not _num(sc.get(k)) or sc.get(k) <= 0:
                p.append(f"scenarios.{k} must be a finite number > 0")
        yrs = sc.get("years", 5)
        if not (isinstance(yrs, int) and not isinstance(yrs, bool) and yrs >= 1):
            p.append(f"scenarios.years must be a whole number >= 1, got {yrs!r}")
        if not sc.get("cases"):
            p.append("scenarios.cases must list at least one case")
        for i, cs in enumerate(sc.get("cases", [])):
            if not (_num(cs.get("growth")) and cs["growth"] > -100):
                p.append(f"scenarios.cases[{i}].growth must be a finite number > -100")
            if not (_num(cs.get("pe")) and cs["pe"] > 0):
                p.append(f"scenarios.cases[{i}].pe must be a finite number > 0")
        tr = sc.get("target_return")
        if tr is not None and not (_num(tr) and tr > -100):
            p.append("scenarios.target_return must be a finite number > -100")
        for x in sc.get("need_at_pe", []):
            if not (_num(x) and x > 0):
                p.append(f"scenarios.need_at_pe values must be > 0, got {x!r}")
        if sc.get("today_pe") is not None and not (_num(sc["today_pe"]) and sc["today_pe"] > 0):
            p.append("scenarios.today_pe must be > 0")
    h = c.get("history")
    if h:
        n = len(h.get("years", []))
        for s_ in h.get("series", []):
            if len(s_.get("values", [])) != n or not all(_num(v) for v in s_.get("values", [])):
                p.append(f"history series '{s_.get('name')}' needs {n} numeric values (one per year)")
    q = c.get("quiz")
    if q and q.get("options"):
        if not isinstance(q.get("answer"), int) or not 0 <= q["answer"] < len(q["options"]):
            p.append("quiz.answer must be the index of the correct option")
    return p


def build(ratios_doc, c):
    problems = validate_content(c)
    if problems:
        raise ContentError("Invalid content.json:\n  - " + "\n  - ".join(problems))
    L = dict(DEFAULT_LABELS)
    L.update(c.get("labels", {}))
    ratios = ratios_doc.get("ratios", {})
    chips = "".join(f'<div class="chip"><span>{esc(x["label"])}</span>{esc(x["value"])}</div>'
                    for x in c.get("chips", []))
    lesson = c.get("lesson") or {}
    lesson_html = ""
    if lesson:
        body = "".join(f"<p>{esc(p)}</p>" for p in lesson.get("body", []))
        lesson_html = (f'<section class="lesson"><h2>{esc(L["lesson"])}: {esc(lesson.get("title", ""))}</h2>'
                       f'{body}{simulator(lesson.get("simulator"), L)}</section>')
        lesson_html = lesson_html.replace("class=\"sim\"", f'class="sim" data-peryear="{esc(L["sim_per_year"])}"', 1)
    quiz = c.get("quiz")
    quiz_html = ""
    if quiz and quiz.get("options"):
        opts = "".join(f'<button type="button" class="qopt" data-i="{i}">{esc(o)}</button>'
                       for i, o in enumerate(quiz["options"]))
        quiz_html = (f'<section class="quiz" data-answer="{int(quiz["answer"])}" '
                     f'data-right="{esc(L["quiz_right"])}" data-wrong="{esc(L["quiz_wrong"])}">'
                     f'<h2>{esc(L["quiz"])}</h2><p>{esc(quiz["q"])}</p><div class="qopts">{opts}</div>'
                     f'<p class="qres" aria-live="polite" hidden><b class="qverdict"></b> {esc(quiz.get("explain", ""))}</p></section>')
    elif quiz:
        quiz_html = (f'<section><h2>{esc(L["quiz"])}</h2><p>{esc(quiz["q"])}</p>'
                     f'<details><summary>{esc(L["quiz_show"])}</summary><p>{esc(quiz["a"])}</p></details></section>')
    hist = c.get("history")
    hist_html = (f'<section><h2>{esc(hist.get("title") or L["history"])}</h2>{history_svg(hist)}</section>'
                 if hist else "")
    pos, con = c.get("positives"), c.get("concerns")
    pc_html = ""
    if pos or con:
        pc_html = (f'<section class="two"><div><h2>{esc(L["positives"])}</h2>{items(pos, "good")}</div>'
                   f'<div><h2>{esc(L["concerns"])}</h2>{items(con, "bad")}</div></section>')
    qs = c.get("questions")
    q_html = (f'<section><h2>{esc(L["questions"])}</h2><ol>' +
              "".join(f"<li>{esc(q)}</li>" for q in qs) + "</ol></section>") if qs else ""
    src = c.get("sources", [])
    return f"""<!DOCTYPE html>
<html lang="{esc(c.get('lang', 'en'))}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{esc(c['company'])} · {esc(L['report_title'])}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Mukta:wght@400;600;700&display=swap" rel="stylesheet">
<style>{CSS}</style>
</head>
<body>
<main class="sheet">
  <header class="lab">
    <div class="lab-top"><span>{esc(L['report_title'])}</span><span>{esc(c.get('price_line', ''))}</span></div>
    <h1>{esc(c['company'])}</h1>
    <div class="sym">{esc(c.get('symbol', ''))}</div>
    <div class="meta"><div>{esc(c.get('basis_line', ''))}</div></div>
    <div class="chips">{chips}</div>
  </header>
  <section><h2>{esc(L['business'])}</h2><p>{esc(c.get('business', ''))}</p></section>
  <section>
    <h2>{esc(L['results'])}</h2>
    <div class="rows">{metric_rows(ratios, c.get('metrics', []), L)}</div>
    <p class="note">{esc(L['range_note'])}</p>
  </section>
  {hist_html}
  {events_section(c.get('events'), L)}
  {pc_html}
  {scenario_section(c.get('scenarios'), L)}
  {q_html}
  {lesson_html}
  {quiz_html}
  <footer>
    <strong>{esc(L['sources'])}</strong>
    <ul>{''.join(f'<li>{esc(s)}</li>' for s in src)}</ul>
    <p class="disc">{esc(c.get('disclaimer', ''))}</p>
  </footer>
</main>
<script>{JS}</script>
</body>
</html>"""


def main():
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(1)
    with open(sys.argv[1], encoding="utf-8") as f:
        ratios_doc = json.load(f)
    with open(sys.argv[2], encoding="utf-8") as f:
        content = json.load(f)
    try:
        out = build(ratios_doc, content)
    except ContentError as e:
        print(e, file=sys.stderr)
        sys.exit(2)
    with open(sys.argv[3], "w", encoding="utf-8") as f:
        f.write(out)
    print(sys.argv[3])


if __name__ == "__main__":
    main()
