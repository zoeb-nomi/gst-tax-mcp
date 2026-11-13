import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gst_mcp.core.gstr1 import gstr1_summary

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "priya_pickles"


def test_priya_q2_summary():
    invoices = json.loads((FIXTURES / "outward_invoices_q2_2026.json").read_text())
    out = gstr1_summary(invoices)
    t = out["tables"]
    assert t["4A/4B/4C/6B B2B"]["taxable_value"] == 160500
    assert t["4A/4B/4C/6B B2B"]["count"] == 3
    assert t["6B/6C credit/debit notes (registered)"]["taxable_value"] == -8000
    assert t["5A B2C large (inter-state, above threshold)"]["taxable_value"] == 320000
    assert t["7 B2C others"]["taxable_value"] == 47100
    assert t["6A exports"]["taxable_value"] == 180000
    tot = out["totals_excl_hsn"]
    assert tot["taxable_value"] == 699600
    assert tot["igst"] == 20475
    assert tot["cgst"] == tot["sgst"] == 2752.50
    assert tot["cess"] == 0
