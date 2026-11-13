#!/usr/bin/env python3
"""Score a no-tools baseline against eval/cases.jsonl.

Input : eval/baseline_answers.jsonl, one object per line: {"id": ..., "answer_text": ...}
Output: eval/results_baseline.json and a printed score line.

How an answer is read. The scorer looks for a line starting "Answer:" (the
baseline prompt asks the model to finish with one). If there is none it
falls back to the whole text. Then, by the case's `answer_type`:
  bool   - first standalone yes/no in the scope; else negation/affirmation phrases
  pct    - last number followed by % (else last number)
  rupees - last amount; understands Rs/INR/rupee sign, Indian and Western commas, lakh, crore
  date   - last date; understands 2026-07-22, 22 July 2026, July 22nd 2026, 22/07/2026
  int    - last integer
  choice - composition route: last of s10_2A / 10(2A) or s10_1 / 10(1) in the scope
Tolerance: rupees +-0.5, pct +-0.01, int exact, date exact. Missing answer = wrong.

Usage: python eval/score_baseline.py [--answers PATH] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august",
     "september", "october", "november", "december"], 1)}
MONTHS.update({k[:3]: v for k, v in list(MONTHS.items())})
MONTHS["sept"] = 9


def _scope(text: str) -> str:
    hits = re.findall(r"(?im)^\s*\**answer\**\s*[:\-]\s*(.+)$", text)
    if hits:
        return hits[-1]
    # Baseline answers are asked to lead with the final answer, then explain.
    # Score the first sentence only, so a number from the explanation (the
    # taxable value, a sub-total) is never mistaken for the answer.
    first = re.split(r"(?<!Rs)(?<!Rs )(?<!\bNo)\.\s+(?=[A-Z])", text.strip(), maxsplit=1)[0]
    return first or text


def parse_bool(text: str):
    s = _scope(text).lower()
    m = re.search(r"\b(yes|no)\b", s)
    if m:
        return m.group(1) == "yes"
    neg = r"not (required|mandatory|eligible|available|allowed|applicable|compulsory|liable|needed)|need not|no need|cannot|can't|isn't|is not|ineligible|exempt"
    pos = r"required|mandatory|eligible|available|allowed|applicable|compulsory|liable|must|can "
    if re.search(neg, s):
        return False
    if re.search(pos, s):
        return True
    return None


def _num(tok: str) -> float:
    return float(tok.replace(",", ""))


def parse_rupees(text: str):
    s = _scope(text)
    found = []
    for m in re.finditer(r"(?i)(?:rs\.?|inr|₹)?\s*([0-9][0-9,]*(?:\.[0-9]+)?)\s*(lakhs?|lacs?|crores?|cr\b)?", s):
        try:
            v = _num(m.group(1))
        except ValueError:
            continue
        unit = (m.group(2) or "").lower()
        if unit.startswith(("lakh", "lac")):
            v *= 1e5
        elif unit.startswith("cr"):
            v *= 1e7
        found.append(v)
    return found[-1] if found else None


def parse_pct(text: str):
    s = _scope(text)
    ps = re.findall(r"([0-9]+(?:\.[0-9]+)?)\s*(?:%|per\s*cent|percent)", s, flags=re.I)
    if ps:
        return float(ps[-1])
    ns = re.findall(r"[0-9]+(?:\.[0-9]+)?", s)
    return float(ns[-1]) if ns else None


def parse_int(text: str):
    ns = re.findall(r"\b[0-9]+\b", _scope(text))
    return int(ns[-1]) if ns else None


def parse_date(text: str):
    s = _scope(text)
    found = []  # (position, date)
    for m in re.finditer(r"\b(20[0-9]{2})-([0-9]{2})-([0-9]{2})\b", s):
        found.append((m.start(), (int(m.group(1)), int(m.group(2)), int(m.group(3)))))
    for m in re.finditer(r"\b([0-9]{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?([A-Za-z]{3,9})\.?,?\s+(20[0-9]{2})\b", s):
        mo = MONTHS.get(m.group(2).lower())
        if mo:
            found.append((m.start(), (int(m.group(3)), mo, int(m.group(1)))))
    for m in re.finditer(r"\b([A-Za-z]{3,9})\.?\s+([0-9]{1,2})(?:st|nd|rd|th)?,?\s+(20[0-9]{2})\b", s):
        mo = MONTHS.get(m.group(1).lower())
        if mo:
            found.append((m.start(), (int(m.group(3)), mo, int(m.group(2)))))
    for m in re.finditer(r"\b([0-9]{1,2})[/.]([0-9]{1,2})[/.](20[0-9]{2})\b", s):
        found.append((m.start(), (int(m.group(3)), int(m.group(2)), int(m.group(1)))))
    for _, (y, mo, d) in sorted(found, reverse=True):
        try:
            return date(y, mo, d).isoformat()
        except ValueError:
            continue
    return None


def parse_choice(text: str):
    s = _scope(text)
    found = [(m.start(), "s10_2A") for m in re.finditer(r"10\s*\(\s*2A\s*\)|s10_2A", s, re.I)]
    found += [(m.start(), "s10_1") for m in re.finditer(r"10\s*\(\s*1\s*\)|s10_1\b", s, re.I)]
    return max(found)[1] if found else None


PARSERS = {"choice": parse_choice, "bool": parse_bool, "rupees": parse_rupees, "pct": parse_pct, "int": parse_int, "date": parse_date}


def matches(atype: str, expected, got) -> bool:
    if got is None:
        return False
    if atype == "bool":
        return got is expected
    if atype == "rupees":
        return abs(float(got) - float(expected)) <= 0.5
    if atype == "pct":
        return abs(float(got) - float(expected)) <= 0.01
    if atype == "int":
        return int(got) == int(expected)
    return got == expected


def score(cases: list[dict], answers: dict[str, str]) -> dict:
    rows = []
    for c in cases:
        key = next(iter(c["expected"]))  # every case has one checkable field
        exp = c["expected"][key]
        text = answers.get(c["id"])
        got = PARSERS[c["answer_type"]](text) if text else None
        rows.append({"id": c["id"], "category": c["category"], "answer_type": c["answer_type"],
                     "expected": exp, "extracted": got, "answered": bool(text),
                     "correct": bool(text) and matches(c["answer_type"], exp, got)})
    n = len(rows)
    ok = sum(r["correct"] for r in rows)
    cats: dict[str, list[int]] = {}
    for r in rows:
        s = cats.setdefault(r["category"], [0, 0]); s[0] += r["correct"]; s[1] += 1
    return {"summary": {"correct": ok, "total": n, "answered": sum(r["answered"] for r in rows),
                        "score": round(ok / n, 4) if n else 0.0,
                        "by_category": {k: {"correct": v[0], "total": v[1]} for k, v in sorted(cats.items())}},
            "results": rows}


def load_cases() -> list[dict]:
    return [json.loads(l) for l in (HERE / "cases.jsonl").read_text().splitlines() if l.strip()]


def load_answers(path: Path) -> dict[str, str]:
    out = {}
    for l in path.read_text().splitlines():
        if l.strip():
            o = json.loads(l)
            out[o["id"]] = o.get("answer_text", "")
    return out


# id -> (fake answer text, should it score correct?)  -- exercises every parser and several formats
DRY = {
    "REG-01": ("Yes, you must register because Rs 42 lakh exceeds Rs 40 lakh.\nAnswer: Yes", True),
    "REG-02": ("No. The limit is 40 lakh so you are not required to register.", False),
    "REG-03": ("Not required - below the threshold for your State. Answer: no", True),
    "RATE-01": ("Cement was in the 28% slab before the reforms.\nAnswer: 28%", True),
    "RATE-02": ("It was cut from 28% to 18% on this date. Answer: 18 percent", True),
    "RATE-03": ("Toilet soap is taxed at 12%.", False),
    "LIAB-01": ("CGST = 9% of 1,00,000 = Rs 9,000.\nAnswer: Rs 9,000", True),
    "LIAB-02": ("IGST at 18% comes to ₹18,000.00", True),
    "LIAB-03": ("Taxable value is 2,40,000 so IGST is Rs 43,500", False),
    "ITR-04": ("Total tax is Rs 1.5 lakh approximately.", False),
    "RCM-01": ("GST payable by company: INR 18,000", True),
    "DL-01": ("It falls due on 20 November 2026.", True),
    "DL-02": ("The due date is July 13th, 2026.", True),
    "DL-03": ("22/07/2026", True),
    "DL-04": ("Answer: 2026-07-22", False),
    "EINV-03": ("You need to show 6-digit HSN codes.", True),
    "DL-07": ("No, IFF is not available for the third month.", True),
    "SCOMP-07": ("Services are within Rs 5 lakh, so not 10(2A).\nAnswer: section 10(1)", True),
}


def dry_run() -> int:
    cases = load_cases()
    ids = {c["id"] for c in cases}
    missing = set(DRY) - ids
    if missing:
        print(f"dry-run: ids not in cases.jsonl: {sorted(missing)}"); return 2
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "fake_answers.jsonl"
        p.write_text("\n".join(json.dumps({"id": i, "answer_text": t[0]}) for i, t in DRY.items()))
        res = score([c for c in cases if c["id"] in DRY], load_answers(p))
    bad = [r["id"] for r in res["results"] if r["correct"] != DRY[r["id"]][1]]
    # also check that an unanswered case counts as wrong
    res2 = score(cases[:1], {})
    if res2["summary"]["correct"] != 0:
        bad.append("unanswered-case")
    if bad:
        print(f"DRY RUN FAILED: unexpected verdicts for {bad}")
        for r in res["results"]:
            print("  ", r)
        return 1
    print(f"DRY RUN OK: all {res['summary']['total']} fake answers scored as designed "
          f"({res['summary']['correct']} correct, {res['summary']['total'] - res['summary']['correct']} wrong; parsers: bool, pct, rupees, date, int, choice; unanswered = wrong)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--answers", default=str(HERE / "baseline_answers.jsonl"))
    ap.add_argument("--dry-run", action="store_true", help="score a built-in fake answers file and check the verdicts")
    a = ap.parse_args()
    if a.dry_run:
        return dry_run()
    path = Path(a.answers)
    if not path.exists():
        print(f"no answers file at {path}; expected lines like {{\"id\": \"REG-01\", \"answer_text\": \"...\"}}")
        return 2
    cases = load_cases()
    res = score(cases, load_answers(path))
    (HERE / "results_baseline.json").write_text(json.dumps(res, indent=2))
    s = res["summary"]
    print(f"BASELINE SCORE: {s['correct']}/{s['total']} = {s['score']:.1%} (answered {s['answered']})")
    for k, v in s["by_category"].items():
        print(f"  {k}: {v['correct']}/{v['total']}")
    for r in res["results"]:
        if not r["correct"]:
            print(f"WRONG {r['id']}: expected {r['expected']} extracted {r['extracted']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
