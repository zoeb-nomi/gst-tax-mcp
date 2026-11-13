"""GST MCP server: 9 tools over stdio (FastMCP)."""
from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from .core.applicability import check_applicability
from .core.classification import classify
from .core.deadlines import filing_deadlines
from .core.einvoice import validate_einvoice
from .core.gstr1 import gstr1_summary
from .core.gstin import validate_gstin
from .core.itc import reconcile_itc
from .core.itr_crossover import (compute_tax, itr_advance_tax_estimate,
                                 itr_turnover_reconcile, presumptive_check)
from .core.liability import LineItem, compute_invoice_liability

mcp = FastMCP("gst-tax-mcp")


def _safe_path(text: str):
    """Return a JSON file path only if it sits inside the allowed root.

    The root is GST_MCP_ROOT if set, otherwise the directory the server was
    started from. A client cannot use a tool argument to read files elsewhere.
    """
    root = Path(os.environ.get("GST_MCP_ROOT", os.getcwd())).resolve()
    try:
        path = (root / text).resolve() if not Path(text).is_absolute() else Path(text).resolve()
    except (OSError, ValueError):
        return None
    if path.suffix.lower() != ".json" or not path.is_file():
        return None
    try:
        path.relative_to(root)
    except ValueError:
        return None
    return path


def _as_dict(raw, key_hint: str):
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        text = raw.strip()
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
        path = _safe_path(text)
        if path is not None:
            return json.loads(path.read_text())
    raise ValueError(f"expected a JSON object or file path for {key_hint}")


def _as_list(raw, key_hint: str):
    if raw is None:
        return []
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str):
        text = raw.strip()
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            pass
        path = _safe_path(text)
        if path is not None:
            return json.loads(path.read_text())
    raise ValueError(f"expected a JSON array or file path for {key_hint}")


@mcp.tool()
def gst_applicability(profile: str) -> dict:
    """Does this business need GST registration, and is it eligible for the
    composition scheme? `profile` is a JSON object (or path to one):
    aggregate_turnover_prior_fy, state_code, supplies_goods, supplies_services,
    inter_state_supply, sells_via_ecommerce, casual_taxable_person,
    composition_scheme_interest. Optional for the composition answer:
    services_turnover_prior_fy, supplies_restaurant_service,
    supplies_services_via_ecommerce, makes_exempt_supplies,
    non_resident_taxable_person, goods_hsn (list). Service providers get the
    s.10(2A) route (Rs 50 lakh, 6%); every rule row cites its source."""
    return check_applicability(_as_dict(profile, "profile"))


@mcp.tool()
def classify_hsn_sac(code: str, on_date: str = "") -> dict:
    """Classify an HSN (goods) or SAC (services) code and return the GST rate
    in force on the given date (default today), with the rate history."""
    on = date.fromisoformat(on_date) if on_date else None
    return classify(code, on)


@mcp.tool()
def calc_gst_liability(invoice: str) -> dict:
    """Compute GST for an invoice. `invoice` is a JSON object (or file path)
    with `lines`: [{description, hsn_sac, quantity, unit_price, discount,
    place_of_supply_state, supplier_state, reverse_charge, on_date(optional
    ISO date)}]. Returns per-line tax and totals (CGST/SGST or IGST, cess,
    reverse-charge liability)."""
    data = _as_dict(invoice, "invoice")
    lines = []
    for raw in data.get("lines", []):
        on = raw.get("on_date")
        lines.append(LineItem(
            description=str(raw.get("description", "")),
            hsn_sac=str(raw.get("hsn_sac", "")),
            quantity=float(raw.get("quantity", 1)),
            unit_price=float(raw.get("unit_price", 0)),
            discount=float(raw.get("discount", 0) or 0),
            place_of_supply_state=str(raw.get("place_of_supply_state", "27")),
            supplier_state=str(raw.get("supplier_state", "27")),
            reverse_charge=bool(raw.get("reverse_charge", False)),
            on_date=date.fromisoformat(on) if on else None,
        ))
    return compute_invoice_liability(lines)


@mcp.tool()
def reconcile_itc_tool(books: str, gstr2b: str, tolerance: float = 1.0) -> dict:
    """Reconcile input tax credit in the books against GSTR-2B. Each of
    `books` and `gstr2b` is a JSON array (or a file path): rows of
    {supplier_gstin, invoice_number, invoice_date, taxable_value, itc_amount,
    hsn_sac}. Flags missing invoices, mismatches beyond `tolerance` rupees and
    section 17(5) blocked credits."""
    return reconcile_itc(_as_list(books, "books"), _as_list(gstr2b, "gstr2b"), tolerance)


@mcp.tool()
def gst_filing_deadlines(period: str, filer_type: str = "monthly",
                         state_code: str = "27",
                         turnover_above_5cr: bool = False) -> dict:
    """Filing due dates for a period. `period` is "YYYY-MM" (month or IFF),
    "YYYY-Q1".."YYYY-Q4" (quarter), or "FY2026-27" (annual + ITR).
    `filer_type`: monthly | qrmp (quarterly return, monthly payment) | composition."""
    return {"period": period, "filer_type": filer_type,
            "state_code": state_code,
            "deadlines": filing_deadlines(period, filer_type, state_code,
                                          turnover_above_5cr)}


@mcp.tool()
def gstr1_summary_tool(invoices: str) -> dict:
    """Summarise an outward-supply register into GSTR-1 table buckets (B2B,
    B2C large, B2C others, exports, SEZ, credit/debit notes, HSN memo).
    `invoices` is a JSON array (or file path)."""
    return gstr1_summary(_as_list(invoices, "invoices"))


@mcp.tool()
def validate_einvoice_tool(einvoice: str, supplier_ato: float = 0.0) -> dict:
    """Validate an e-invoice payload: IRN hash format, GSTIN format and
    checksum, mandatory fields, HSN digit requirements for the supplier's
    aggregate turnover (`supplier_ato`), tax math and invoice totals."""
    return validate_einvoice(_as_dict(einvoice, "einvoice"), supplier_ato)


@mcp.tool()
def itr_turnover_reconcile_tool(gstr3b_turnover: float,
                                itr_gross_receipts: float,
                                itr_presumptive_scheme: str = "none") -> dict:
    """ITR crossover: reconcile GSTR-3B annual turnover against the ITR
    gross receipts; flags variance beyond 5% and presumptive-limit breaches."""
    return itr_turnover_reconcile(gstr3b_turnover, itr_gross_receipts,
                                  itr_presumptive_scheme)


@mcp.tool()
def itr_advance_tax_estimate_tool(annual_income_projection: float,
                                  regime: str = "new") -> dict:
    """ITR crossover: estimate the annual tax and quarterly advance-tax
    instalments from a projected annual income (new or old regime), and
    compare regimes."""
    estimate = itr_advance_tax_estimate(annual_income_projection, regime)
    new = compute_tax(annual_income_projection, "new")
    old = compute_tax(annual_income_projection, "old")
    estimate["regime_comparison"] = {
        "new_regime_total_tax": new["total_tax"],
        "old_regime_total_tax": old["total_tax"],
        "recommended": "new" if new["total_tax"] <= old["total_tax"] else "old",
    }
    return estimate


TOOLS = [gst_applicability, classify_hsn_sac, calc_gst_liability,
         reconcile_itc_tool, gst_filing_deadlines, gstr1_summary_tool,
         validate_einvoice_tool, itr_turnover_reconcile_tool,
         itr_advance_tax_estimate_tool]

def main() -> None:
    """Console-script entry point: serve the nine tools over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
