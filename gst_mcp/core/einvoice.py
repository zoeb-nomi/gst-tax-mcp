"""E-invoice (IRN) validation against the e-invoice schema essentials."""
from __future__ import annotations

import re
from datetime import date

from .data import EINVOICE_MANDATE
from .gstin import validate_gstin

_IRN = re.compile(r"^[0-9a-f]{64}$")


def _hsn_digits_required(ato: float) -> int:
    return 6 if ato > EINVOICE_MANDATE["ato_threshold"] else 4


def validate_einvoice(doc: dict, supplier_ato: float = 0.0, as_of: date | None = None) -> dict:
    """Validate one e-invoice payload's mandatory fields.

    doc keys: irn, irp?, doc_type, doc_number, doc_date, seller_gstin,
    buyer_gstin, place_of_supply, items: [{hsn_sac, hsn?, qty?, unit_price,
    taxable_value, rate_pct, cgst?, sgst?, igst?, cess?}], total_invoice_value.
    """
    errors: list[str] = []
    warnings: list[str] = []
    as_of = as_of or date.today()

    irn = str(doc.get("irn", "") or "").strip().lower()
    if not irn:
        errors.append("IRN missing: an e-invoice must carry a 64-character hash (IRN)")
    elif not _IRN.match(irn):
        errors.append("IRN must be 64 hexadecimal characters")

    seller = validate_gstin(str(doc.get("seller_gstin", "") or ""))
    buyer = validate_gstin(str(doc.get("buyer_gstin", "") or ""))
    if not seller["valid"]:
        errors.append(f"seller GSTIN invalid: {'; '.join(seller['errors'])}")
    if not buyer["valid"]:
        errors.append(f"buyer GSTIN invalid: {'; '.join(buyer['errors'])}")

    if not str(doc.get("doc_number", "") or "").strip():
        errors.append("invoice number (doc_number) missing")
    if not str(doc.get("doc_date", "") or "").strip():
        errors.append("invoice date (doc_date) missing")

    place = str(doc.get("place_of_supply", "") or "").strip()
    if len(place) != 2:
        errors.append("place_of_supply must be the 2-digit state code")

    items = doc.get("items") or []
    if not items:
        errors.append("at least one item line is required")
    need_digits = _hsn_digits_required(supplier_ato)
    for idx, item in enumerate(items, 1):
        hsn = str(item.get("hsn_sac", item.get("hsn", "")) or "").strip()
        if not hsn:
            errors.append(f"item {idx}: HSN/SAC missing")
        elif len(hsn) < need_digits:
            errors.append(f"item {idx}: HSN/SAC shorter than the {need_digits} digits "
                          f"required for your aggregate turnover")
        taxable = float(item.get("taxable_value", 0) or 0)
        rate = float(item.get("rate_pct", 0) or 0)
        tax = (float(item.get("cgst", 0) or 0) + float(item.get("sgst", 0) or 0)
               + float(item.get("igst", 0) or 0) + float(item.get("cess", 0) or 0))
        expected = round(taxable * rate / 100, 2)
        if rate and abs(tax - expected) > 1.0:
            errors.append(f"item {idx}: tax lines ({tax}) do not match "
                          f"taxable x rate ({expected})")

    total = float(doc.get("total_invoice_value", 0) or 0)
    item_total = round(sum(float(i.get("taxable_value", 0) or 0)
                           + float(i.get("cgst", 0) or 0) + float(i.get("sgst", 0) or 0)
                           + float(i.get("igst", 0) or 0) + float(i.get("cess", 0) or 0)
                           for i in items), 2)
    if abs(total - item_total) > 1.0:
        errors.append(f"total_invoice_value ({total}) != sum of items ({item_total})")

    if seller.get("valid") and buyer.get("valid") and seller["state_code"] == buyer["state_code"]:
        cgst = sum(float(i.get("cgst", 0) or 0) for i in items)
        igst = sum(float(i.get("igst", 0) or 0) for i in items)
        if igst and not cgst:
            warnings.append("buyer is in the same state as seller but IGST charged "
                            "(check place of supply)")
    return {"valid": not errors, "errors": errors, "warnings": warnings,
            "hsn_digits_required": need_digits, "checked_fields": len(items) + 6}
