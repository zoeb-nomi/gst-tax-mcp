#!/usr/bin/env python3
"""Run every case in eval/cases.jsonl through the matching tool and compare.

Usage (from the repo root):  python eval/run_tools.py
No network, no keys. Writes eval/results_tools.json.

Tools are called through the functions in gst_mcp.server (the same code the
MCP clients hit). `presumptive_check` is a core function that the server does
not expose; it is called from gst_mcp.core.itr_crossover.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

from gst_mcp import server  # noqa: E402
from gst_mcp.core.itr_crossover import presumptive_check  # noqa: E402


def _find(deadlines: list[dict], prefix: str, exclude: str | None = None):
    for d in deadlines:
        form = d["form"]
        if form.startswith(prefix) and not (exclude and exclude in form):
            return d
    return None


def call(tool: str, args: dict):
    """Invoke the tool; JSON-typed params are passed as JSON strings like an MCP client would."""
    if tool == "gst_applicability":
        return server.gst_applicability(json.dumps(args["profile"]))
    if tool == "classify_hsn_sac":
        return server.classify_hsn_sac(args["code"], args.get("on_date", ""))
    if tool == "calc_gst_liability":
        return server.calc_gst_liability(json.dumps(args["invoice"]))
    if tool == "reconcile_itc_tool":
        return server.reconcile_itc_tool(json.dumps(args["books"]), json.dumps(args["gstr2b"]))
    if tool == "gst_filing_deadlines":
        return server.gst_filing_deadlines(args["period"], args.get("filer_type", "monthly"),
                                           args.get("state_code", "27"),
                                           args.get("turnover_above_5cr", False))
    if tool == "gstr1_summary_tool":
        return server.gstr1_summary_tool(json.dumps(args["invoices"]))
    if tool == "validate_einvoice_tool":
        return server.validate_einvoice_tool(json.dumps(args["einvoice"]), args.get("supplier_ato", 0.0))
    if tool == "itr_turnover_reconcile_tool":
        return server.itr_turnover_reconcile_tool(args["gstr3b_turnover"], args["itr_gross_receipts"],
                                                  args.get("itr_presumptive_scheme", "none"))
    if tool == "itr_advance_tax_estimate_tool":
        return server.itr_advance_tax_estimate_tool(args["annual_income_projection"], args.get("regime", "new"))
    if tool == "presumptive_check":
        return presumptive_check(args["turnover"], args.get("scheme", "44AD"),
                                 args.get("digital_receipt_share", 1.0))
    raise ValueError(f"unknown tool {tool}")


def extract(tool: str, result: dict, key: str):
    """Map an `expected` key to the value in the tool's output (None if absent)."""
    if tool == "gst_applicability":
        if key == "composition_rate_total":
            return (result.get("composition_rate") or {}).get("total")
        return result.get(key)
    if tool == "classify_hsn_sac":
        app = result.get("applicable") or {}
        return {"rate": app.get("rate"), "cess": app.get("cess")}.get(key)
    if tool == "calc_gst_liability":
        return result["totals"].get(key)
    if tool == "reconcile_itc_tool":
        return result["summary"].get(key)
    if tool == "gst_filing_deadlines":
        dl = result["deadlines"]
        if key == "gstr3b_due":
            d = _find(dl, "GSTR-3B")
        elif key == "gstr1_due":
            d = _find(dl, "GSTR-1", exclude="IFF")
        elif key == "iff_due":
            d = _find(dl, "GSTR-1 IFF")
        elif key == "iff_available":
            d = _find(dl, "GSTR-1 IFF")
            return bool(d and d.get("due_date"))
        else:
            return None
        return d.get("due_date") if d else None
    if tool == "gstr1_summary_tool":
        if key == "b2c_large_reported":
            return any(name.startswith("5A") and t["count"] > 0 for name, t in result["tables"].items())
        return None
    if tool == "validate_einvoice_tool":
        return result.get(key)
    if tool == "presumptive_check":
        return result.get(key)
    if tool == "itr_advance_tax_estimate_tool":
        return result.get(key)
    return None


def same(expected, actual) -> bool:
    if isinstance(expected, bool) or isinstance(actual, bool):
        return expected is actual
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        return abs(float(expected) - float(actual)) <= 0.01
    return expected == actual


def main() -> int:
    cases = [json.loads(l) for l in (HERE / "cases.jsonl").read_text().splitlines() if l.strip()]
    rows, mism = [], []
    for c in cases:
        try:
            out = call(c["tool"], c["tool_args"])
            got = {k: extract(c["tool"], out, k) for k in c["expected"]}
            err = None
        except Exception as e:  # a crash is a mismatch, not a reason to stop
            out, got, err = None, {k: None for k in c["expected"]}, f"{type(e).__name__}: {e}"
        ok = err is None and all(same(c["expected"][k], got[k]) for k in c["expected"])
        row = {"id": c["id"], "category": c["category"], "tool": c["tool"], "expected": c["expected"],
               "tool_output": got, "pass": ok, "source": c["source"], "confidence": c["confidence"]}
        if err:
            row["error"] = err
        if not ok and out is not None:
            if c["tool"] == "classify_hsn_sac":
                row["note"] = (out.get("applicable") or {}).get("desc") or out.get("error")
            elif c["tool"] == "calc_gst_liability":
                row["note"] = out["lines"][0].get("error") or out["lines"][0].get("rate_row")
        rows.append(row)
        if not ok:
            mism.append(row)
    passed = sum(r["pass"] for r in rows)
    cats: dict[str, list[int]] = {}
    for r in rows:
        s = cats.setdefault(r["category"], [0, 0])
        s[0] += r["pass"]; s[1] += 1
    summary = {"passed": passed, "total": len(rows), "score": round(passed / len(rows), 4),
               "by_category": {k: {"passed": v[0], "total": v[1]} for k, v in sorted(cats.items())}}
    (HERE / "results_tools.json").write_text(json.dumps({"summary": summary, "results": rows}, indent=2, default=str))
    print(f"TOOL SCORE: {passed}/{len(rows)} = {summary['score']:.1%}")
    for k, v in summary["by_category"].items():
        print(f"  {k}: {v['passed']}/{v['total']}")
    for r in mism:
        extra = f" | {r.get('error') or r.get('note') or ''}"
        print(f"MISMATCH {r['id']}: expected {r['expected']} got {r['tool_output']}{extra}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
