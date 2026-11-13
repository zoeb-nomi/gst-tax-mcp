"""HSN / SAC classification against the curated rate table."""
from __future__ import annotations

from datetime import date

from .data import RATE_TABLE


def _matches(prefix: str, code: str) -> bool:
    return code.startswith(prefix)


def classify(code: str, on_date: date | None = None) -> dict:
    """Classify an HSN (goods) or SAC (services) code and return the applicable rate.

    Returns the rate row effective on `on_date` (default: today) plus the
    history of rows that ever applied to this prefix.
    """
    code = (code or "").strip().replace(" ", "")
    if not code:
        return {"input": code, "matches": [], "applicable": None, "error": "empty code"}
    as_of = on_date or date.today()
    hits = [row for row in RATE_TABLE if _matches(row["prefix"], code)]
    if not hits:
        return {"input": code, "matches": [], "applicable": None,
                "error": "no curated table entry; verify against CBIC notifications"}
    effective = [row for row in hits if row["effective_from"] <= as_of]
    applicable, alternatives = None, []
    if effective:
        # Most specific prefix wins (e.g. 870321 over 8703); within it, the latest
        # row in force. If several rows tie (a conditional split such as pre-packaged
        # vs loose rice), answer with the highest-rate row and list the rest as
        # `alternatives`, so the caller sees the condition rather than a silent nil.
        longest = max(len(r["prefix"]) for r in effective)
        specific = [r for r in effective if len(r["prefix"]) == longest]
        latest = max(r["effective_from"] for r in specific)
        tied = [r for r in specific if r["effective_from"] == latest]
        tied.sort(key=lambda r: (-r["rate"], -r["cess"]))
        applicable, alternatives = tied[0], tied[1:]
    goods = code[0].isdigit() and code[:2] < "99"
    return {
        "input": code,
        "kind": "HSN (goods)" if goods else "SAC (services)",
        "applicable": applicable,
        "alternatives": alternatives,
        "history": sorted(hits, key=lambda r: r["effective_from"]),
        "as_of": as_of.isoformat(),
    }
