#!/usr/bin/env python3
"""
Check that two language versions of a report's content.json carry the same numbers.

Usage:
    python3 check_consistency.py content_en.json content_mr.json

Rules:
- Both files must have the same structure (same keys, same list lengths),
  apart from "labels" and "lang", which are skipped.
- Every number field must be identical.
- Every text field must contain the same multiset of numbers (Latin digits;
  commas in 3,787 or 1,48,461 are ignored). Words may differ, numbers may not.
Exit code 0 = consistent, 1 = problems found (each one is printed).
"""
import json
import re
import sys

SKIP = {"labels", "lang"}
# Optional sign (hyphen, Unicode minus or plus) or accounting parentheses, then digits.
NUM = re.compile(r"(\()?([-−+])?\s?₹?\s?(\d+(?:[.,]\d+)*)(\))?")


def numbers(text):
    """Signed numbers in text. '−27%' and '+27%' differ; '(27)' (accounting style) is -27.
    Hyphens between two numbers ('38–40', '2025-26') are treated as ranges, not signs."""
    out = []
    for m in NUM.finditer(text):
        lp, sign, num, rp = m.groups()
        v = float(num.replace(",", ""))
        start = m.start(2) if sign else m.start(3)
        prev = text[start - 1] if start > 0 else " "
        if sign in ("-", "−") and not prev.isdigit():
            v = -v
        if lp and rp:
            v = -v
        out.append(v)
    return sorted(out)


def walk(a, b, path, problems):
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            if k in SKIP and path == "":
                continue
            if k not in a or k not in b:
                problems.append(f"{path}/{k}: present in only one file")
                continue
            walk(a[k], b[k], f"{path}/{k}", problems)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            problems.append(f"{path}: {len(a)} items vs {len(b)} items")
        for i, (x, y) in enumerate(zip(a, b)):
            walk(x, y, f"{path}[{i}]", problems)
    elif isinstance(a, str) and isinstance(b, str):
        na, nb = numbers(a), numbers(b)
        if na != nb:
            problems.append(f"{path}: numbers differ\n    A: {na}  «{a[:90]}»\n    B: {nb}  «{b[:90]}»")
    elif isinstance(a, (int, float)) and isinstance(b, (int, float)):
        if a != b:
            problems.append(f"{path}: {a} vs {b}")
    elif type(a) is not type(b):
        problems.append(f"{path}: different types ({type(a).__name__} vs {type(b).__name__})")


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(2)
    a = json.load(open(sys.argv[1], encoding="utf-8"))
    b = json.load(open(sys.argv[2], encoding="utf-8"))
    problems = []
    walk(a, b, "", problems)
    if problems:
        print(f"{len(problems)} consistency problem(s):")
        for p in problems:
            print(" -", p)
        sys.exit(1)
    print("Consistent: same structure and same numbers in both files.")


if __name__ == "__main__":
    main()
