"""GSTR-1 summary: bucket invoices into the standard outward-supply tables."""
from __future__ import annotations

from collections import defaultdict


def _b2cl_threshold(invoice_date: str) -> int:
    """Rs 2.5L before the Aug 2024 tax period, Rs 1L from it (Notif 12/2024-CT)."""
    return 2_50_000 if invoice_date and invoice_date < "2024-08-01" else 1_00_000


def gstr1_summary(invoices: list[dict]) -> dict:
    """Summarise an outward-supply register into GSTR-1 table buckets.

    Each invoice: {
      invoice_number, invoice_date (ISO), customer_gstin (or ""),
      customer_state (2-char code), supplier_state (2-char code),
      place_of_supply (2-char code), taxable_value, rate_pct,
      cgst, sgst, igst, cess, export (bool), sez (bool),
      document_type: "invoice" | "credit_note" | "debit_note"
    }
    """
    tables: dict[str, dict] = defaultdict(lambda: {"count": 0, "taxable_value": 0.0,
                                                   "cgst": 0.0, "sgst": 0.0,
                                                   "igst": 0.0, "cess": 0.0})

    def _add(table: str, inv: dict) -> None:
        bucket = tables[table]
        bucket["count"] += 1
        for f in ("taxable_value", "cgst", "sgst", "igst", "cess"):
            bucket[f] = round(bucket[f] + float(inv.get(f, 0) or 0), 2)

    for inv in invoices:
        taxable = float(inv.get("taxable_value", 0) or 0)
        sign = -1.0 if inv.get("document_type") == "credit_note" else 1.0
        signed = {**inv, "taxable_value": round(sign * taxable, 2)}
        for f in ("cgst", "sgst", "igst", "cess"):
            signed[f] = round(sign * float(inv.get(f, 0) or 0), 2)
        gstin = str(inv.get("customer_gstin", "") or "")
        if inv.get("export"):
            _add("6A exports", signed)
        elif inv.get("sez") or inv.get("sez_unit"):
            _add("6B/6C SEZ supplies", signed)
        elif inv.get("document_type") in ("credit_note", "debit_note"):
            _add("6B/6C credit/debit notes (registered)", signed)
        elif len(gstin) == 15:
            _add("4A/4B/4C/6B B2B", signed)
        else:
            pos = str(inv.get("place_of_supply", inv.get("customer_state", "")) or "")
            value_signed = signed["taxable_value"]
            # Invoice-wise (Table 5) reporting of inter-State B2C supplies: invoice value
            # above Rs 2.5L, lowered to Rs 1L from the Aug 2024 period by Notification
            # 12/2024-CT (10 Jul 2024). Invoice value includes tax.
            inv_value = abs(value_signed) + sum(abs(signed[f]) for f in ("cgst", "sgst", "igst", "cess"))
            if inv_value > _b2cl_threshold(str(inv.get("invoice_date", ""))) and \
                    pos != str(inv.get("supplier_state", "")):
                _add("5A B2C large (inter-state, above threshold)", signed)
            else:
                _add("7 B2C others", signed)
        hsn = str(inv.get("hsn_sac", "") or "")
        if hsn:
            hsn_bucket = tables.setdefault(
                "12 HSN summary", {"count": 0, "taxable_value": 0.0, "cgst": 0.0,
                                   "sgst": 0.0, "igst": 0.0, "cess": 0.0})
            hsn_bucket["count"] = 0
            for f in ("taxable_value", "cgst", "sgst", "igst", "cess"):
                hsn_bucket[f] = round(hsn_bucket[f] + float(inv.get(f, 0) or 0), 2)

    totals = {"count": 0, "taxable_value": 0.0, "cgst": 0.0, "sgst": 0.0,
              "igst": 0.0, "cess": 0.0}
    for name, bucket in tables.items():
        if name == "12 HSN summary":
            continue
        for f in totals:
            bucket.setdefault(f, 0.0)
            totals[f] = round(totals[f] + bucket[f], 2) if f != "count" else totals[f] + bucket["count"]

    return {"tables": dict(sorted(tables.items())),
            "totals_excl_hsn": totals,
            "note": "HSN summary (table 12) shown as memo; not added to totals. "
                    "Net of credit notes; verify against books before filing."}
