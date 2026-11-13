import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gst_mcp.core.classification import classify
from gst_mcp.core.liability import LineItem, compute_invoice_liability


def test_rate_changes_with_effective_date():
    before = classify("20059900", date(2025, 9, 21))
    after = classify("20059900", date(2025, 9, 22))
    assert before["applicable"]["rate"] == 12.0
    assert after["applicable"]["rate"] == 5.0
    assert len(after["history"]) == 2


def test_sac_service_classification():
    out = classify("998311", date(2026, 11, 1))
    assert out["kind"] == "SAC (services)"
    assert out["applicable"]["rate"] == 18.0


def test_unknown_code_flags_error():
    out = classify("999999")
    assert out["applicable"] is None
    assert "error" in out


def test_intra_state_split():
    inv = {"lines": [{"description": "pickles", "hsn_sac": "20059900",
                      "quantity": 60, "unit_price": 625,
                      "place_of_supply_state": "27", "supplier_state": "27",
                      "on_date": "2026-07-19"}]}
    out = compute_invoice_liability([LineItem(**l) for l in inv["lines"]])
    assert out["totals"]["cgst"] == 937.50
    assert out["totals"]["sgst"] == 937.50
    assert out["totals"]["igst"] == 0.0


def test_inter_state_igst_and_rcm():
    igst_line = LineItem(description="hampers", hsn_sac="20059900", quantity=400,
                         unit_price=1150, place_of_supply_state="07",
                         supplier_state="27", on_date=date(2026, 11, 5))
    rcm_line = LineItem(description="freight GTA", hsn_sac="996511", quantity=1,
                        unit_price=8000, place_of_supply_state="27",
                        supplier_state="27", reverse_charge=True,
                        on_date=date(2026, 7, 15))
    out = compute_invoice_liability([igst_line, rcm_line])
    assert out["totals"]["igst"] == 23000.0
    assert out["totals"]["rcm_liability"] == 400.0
    assert out["totals"]["total_tax"] == 23000.0


def test_rate_history_gst_2_0_and_tobacco():
    from gst_mcp.core.classification import classify
    # Notif 9/2025-CT(Rate): 22 Sep 2025 cars; small car 18%, SUV 40%, no cess either way.
    assert classify("870323", date(2026, 2, 1))["applicable"]["rate"] == 40.0
    assert classify("870323", date(2025, 6, 1))["applicable"]["rate"] == 28.0
    assert classify("870321", date(2026, 2, 1))["applicable"]["rate"] == 18.0
    # Motorcycles <=350cc: no compensation cess before 22 Sep 2025 (Cess Notif 1/2017 S.No.53).
    assert classify("871120", date(2025, 6, 1))["applicable"]["cess"] == 0.0
    # Cigarettes: 28% + cess until 31 Jan 2026, 40% with nil cess from 1 Feb 2026.
    assert classify("240220", date(2026, 1, 31))["applicable"]["rate"] == 28.0
    assert classify("240220", date(2026, 2, 1))["applicable"]["cess"] == 0.0
    # Rice: pre-packaged 5% by default, loose nil-rate listed as an alternative.
    rice = classify("100630", date(2026, 3, 1))
    assert rice["applicable"]["rate"] == 5.0 and rice["alternatives"][0]["rate"] == 0.0
