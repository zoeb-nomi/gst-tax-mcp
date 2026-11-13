"""GST liability computation: CGST/SGST vs IGST, reverse charge, composition."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from .classification import classify


@dataclass
class LineItem:
    description: str
    hsn_sac: str
    quantity: float = 1.0
    unit_price: float = 0.0
    discount: float = 0.0
    place_of_supply_state: str = "27"
    supplier_state: str = "27"
    reverse_charge: bool = False
    on_date: date | None = None

    @property
    def taxable_value(self) -> float:
        return round(self.quantity * self.unit_price - self.discount, 2)


def _split(rate: float) -> tuple[float, float]:
    half = round(rate / 2, 2)
    return half, round(rate - half, 2)


def compute_line_liability(item: LineItem, rate_info: dict | None = None) -> dict:
    """Compute GST for one line item given the rate row from classify()."""
    taxable = item.taxable_value
    on_date = item.on_date
    if isinstance(on_date, str):
        on_date = date.fromisoformat(on_date)
    if rate_info is None:
        rate_info = classify(item.hsn_sac, on_date)
    applicable = rate_info.get("applicable")
    if not applicable:
        return {"line": item.description, "taxable_value": taxable,
                "error": rate_info.get("error", "unclassified"), "rate": None}
    rate = applicable["rate"]
    cess = applicable.get("cess", 0.0)
    inter_state = item.place_of_supply_state != item.supplier_state
    out: dict = {
        "line": item.description,
        "hsn_sac": item.hsn_sac,
        "rate_row": applicable["desc"],
        "effective_from": applicable["effective_from"].isoformat(),
        "taxable_value": taxable,
        "rate_pct": rate,
        "cess_pct": cess,
        "supply_type": "inter-state (IGST)" if inter_state else "intra-state (CGST+SGST)",
        "reverse_charge": item.reverse_charge,
    }
    if item.reverse_charge:
        out["note"] = "Reverse charge: recipient pays GST directly; no tax on the invoice"
        out["tax_on_invoice"] = 0.0
        out["rcm_liability"] = round(taxable * rate / 100, 2)
        return out
    tax = round(taxable * rate / 100, 2)
    cess_amt = round(taxable * cess / 100, 2)
    if inter_state:
        out.update({"igst": tax, "cgst": 0.0, "sgst": 0.0, "cess": cess_amt,
                    "total_tax": round(tax + cess_amt, 2)})
    else:
        cgst, sgst = _split(rate)
        out.update({"igst": 0.0, "cgst": round(taxable * cgst / 100, 2),
                    "sgst": round(taxable * sgst / 100, 2), "cess": cess_amt,
                    "total_tax": round(tax + cess_amt, 2)})
    return out


def compute_invoice_liability(lines: list[LineItem]) -> dict:
    """Aggregate liability across a list of line items."""
    results = [compute_line_liability(li) for li in lines]
    totals = {"taxable_value": 0.0, "cgst": 0.0, "sgst": 0.0, "igst": 0.0,
              "cess": 0.0, "total_tax": 0.0, "rcm_liability": 0.0}
    for r in results:
        if r.get("error"):
            continue
        for k in totals:
            totals[k] = round(totals[k] + r.get(k, 0.0), 2)
    return {"lines": results, "totals": totals}
