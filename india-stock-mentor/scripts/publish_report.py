#!/usr/bin/env python3
"""
One command to build a report safely. Stops at the first failure; nothing is written
to the output folder unless every check passes.

Usage:
    python3 publish_report.py input.json content_en.json [content_mr.json ...] --out OUTDIR

Steps:
  1. ratios.py         input.json -> ratios.json (rejects invalid input)
  2. validate_report   each content file against ratios.json (numbers, EPS baseline, header)
  3. check_consistency the first content file against every other language
  4. build_dashboard   one HTML per content file: OUTDIR/report_<lang>.html
The first content file is the canonical one; the others must be derived from it.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
LANG_RE = re.compile(r"^[a-z]{2,3}(-[A-Za-z0-9]{2,8})*$")


def atomic_swap(stage, out, _replace=os.replace):
    """Move `stage` to `out`. If `out` exists it is kept as a backup until the swap succeeds;
    on any failure the original `out` is restored exactly. `_replace` exists for tests."""
    backup = None
    if os.path.exists(out):
        backup = out + ".previous"
        shutil.rmtree(backup, ignore_errors=True)
        _replace(out, backup)
    try:
        _replace(stage, out)
    except BaseException:
        if backup and not os.path.exists(out):
            os.replace(backup, out)          # put the original back before reporting the error
        raise
    if backup:
        shutil.rmtree(backup, ignore_errors=True)


def step(name, cmd):
    res = subprocess.run([sys.executable, os.path.join(HERE, cmd[0]), *cmd[1:]], capture_output=True, text=True)
    out = (res.stdout + res.stderr).strip()
    if res.returncode != 0:
        print(f"✗ {name}\n{out}\n\nStopped. Nothing was published.", file=sys.stderr)
        sys.exit(1)
    print(f"✓ {name}" + (f"\n  {out}" if out and "warning" in out else ""))
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input")
    ap.add_argument("contents", nargs="+")
    ap.add_argument("--out", required=True)
    ap.add_argument("--dry-run", action="store_true",
                    help="run every check and build in a temporary folder, but don't touch --out")
    a = ap.parse_args()
    with tempfile.TemporaryDirectory() as tmp:
        rj = os.path.join(tmp, "ratios.json")
        res = step("ratios computed", ["ratios.py", a.input])
        with open(rj, "w", encoding="utf-8") as f:
            f.write(res.stdout)
        for c in a.contents:
            step(f"numbers validated: {os.path.basename(c)}", ["validate_report.py", rj, c])
        for c in a.contents[1:]:
            step(f"same numbers as canonical: {os.path.basename(c)}", ["check_consistency.py", a.contents[0], c])
        langs = [json.load(open(c, encoding="utf-8")).get("lang", "en") for c in a.contents]
        bad = [x for x in langs if not (isinstance(x, str) and LANG_RE.match(x))]
        if bad:
            print(f"✗ invalid language code(s) {bad}; use codes like en, mr, hi, mr-IN\n\nStopped. Nothing was published.",
                  file=sys.stderr)
            sys.exit(1)
        dupes = sorted({x for x in langs if langs.count(x) > 1})
        if dupes:
            print(f"✗ two content files share the same lang {dupes}; each language needs its own file\n\nStopped. Nothing was published.",
                  file=sys.stderr)
            sys.exit(1)
        built = []
        for c, lang in zip(a.contents, langs):
            dst = os.path.join(tmp, f"report_{lang}.html")
            step(f"report built: {lang}", ["build_dashboard.py", rj, c, dst])
            built.append(dst)
        summary = ", ".join(f"{os.path.basename(b)} ({os.path.getsize(b) / 1024:.0f} KB)" for b in built)
        if a.dry_run:
            print(f"Dry run passed: {len(built)} language(s) would be published to {a.out}: {summary}")
            return
        # Atomic publish: assemble everything in a staging folder next to the destination, then swap it in.
        out = os.path.abspath(a.out)
        parent = os.path.dirname(out)
        os.makedirs(parent, exist_ok=True)
        stage = tempfile.mkdtemp(prefix=".stage-", dir=parent)
        try:
            if os.path.isdir(out):   # keep files that aren't ours (e.g. inputs living in the same folder)
                for f in os.listdir(out):
                    src = os.path.join(out, f)
                    if os.path.isfile(src) and not (f == "ratios.json" or f.startswith("report_")):
                        shutil.copy2(src, os.path.join(stage, f))
            shutil.copy(rj, os.path.join(stage, "ratios.json"))
            for b in built:
                shutil.copy(b, os.path.join(stage, os.path.basename(b)))
            atomic_swap(stage, out)
        except BaseException:
            shutil.rmtree(stage, ignore_errors=True)   # the original output was already restored by atomic_swap
            raise
    print(f"Published {len(built)} language(s) to {a.out}: {summary}")


if __name__ == "__main__":
    main()
