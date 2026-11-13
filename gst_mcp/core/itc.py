"""ITC reconciliation: purchase register (books) vs GSTR-2B, plus 17(5) block checks."""
from __future__ import annotations

from .data import BLOCKED_ITC


def _key(row: dict) -> tuple[str, str]:
    return (str(row.get("supplier_gstin", "")).upper(),
            str(row.get("invoice_number", "")).strip())


def _blocked_reason(hsn_sac: str) -> str | None:
    code = str(hsn_sac or "").strip()
    for rule in BLOCKED_ITC:
        prefix = rule.get("match")
        if prefix and code.startswith(prefix):
            return rule["reason"]
    return None


def reconcile_itc(books: list[dict], gstr2b: list[dict], tolerance: float = 1.0) -> dict:
    """Reconcile input-tax credit claimed in books against GSTR-2B.

    Each row: supplier_gstin, invoice_number, invoice_date, taxable_value,
    itc_amount, hsn_sac (optional), itc_type (cgs/sgst/igst ignored here —
    totals are what matter for the demo).
    """
    books_by_key, b2b_by_key = {}, {}
    for row in books:
        books_by_key.setdefault(_key(row), []).append(row)
    for row in gstr2b:
        b2b_by_key.setdefault(_key(row), []).append(row)

    matched, mismatched, only_books, only_2b = [], [], [], []
    for key, brows in books_by_key.items():
        brow_rows = b2b_by_key.get(key)
        if not brow_rows:
            for row in brows:
                only_books.append({**row, "issue": "in books, missing from GSTR-2B"})
            continue
        book_total = round(sum(float(r.get("itc_amount", 0) or 0) for r in brows), 2)
        b2b_total = round(sum(float(r.get("itc_amount", 0) or 0) for r in brow_rows), 2)
        if abs(book_total - b2b_total) <= tolerance:
            for row in brows:
                matched.append(row)
        else:
            for row in brows:
                mismatched.append({**row, "books_itc": book_total, "gstr2b_itc": b2b_total,
                                   "difference": round(book_total - b2b_total, 2),
                                   "issue": "ITC amount mismatch beyond tolerance"})
    for key, rows in b2b_by_key.items():
        if key not in books_by_key:
            for row in rows:
                only_2b.append({**row, "issue": "in GSTR-2B, not recorded in books"})

    for bucket in (matched, mismatched, only_books, only_2b):
        for row in bucket:
            reason = _blocked_reason(row.get("hsn_sac", ""))
            if reason:
                row["blocked_itc"] = reason
                row["itc_allowed"] = False
            else:
                row["itc_allowed"] = True

    books_total = round(sum(float(r.get("itc_amount", 0) or 0) for r in books), 2)
    b2b_total = round(sum(float(r.get("itc_amount", 0) or 0) for r in gstr2b), 2)
    claimable = round(sum(float(r.get("itc_amount", 0) or 0)
                          for r in matched + only_2b if r.get("itc_allowed")), 2)
    blocked = round(sum(float(r.get("itc_amount", 0) or 0)
                        for r in matched + only_2b if not r.get("itc_allowed")), 2)
    return {
        "summary": {
            "books_itc_total": books_total,
            "gstr2b_itc_total": b2b_total,
            "matched_count": len(matched),
            "mismatched_count": len(mismatched),
            "only_in_books_count": len(only_books),
            "only_in_2b_count": len(only_2b),
            "claimable_itc": claimable,
            "blocked_itc": blocked,
            "recommendation": (
                "ITC agrees with GSTR-2B; safe to claim" if not (mismatched or only_books)
                else "Resolve mismatches before filing GSTR-3B: claim only the matched "
                     "plus in-2B amounts; follow up with suppliers on missing invoices"
            ),
        },
        "matched": matched,
        "mismatched": mismatched,
        "only_in_books": only_books,
        "only_in_2b": only_2b,
    }
