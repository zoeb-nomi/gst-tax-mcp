import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gst_mcp.core.itc import reconcile_itc

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "priya_pickles"


def _load(name):
    return json.loads((FIXTURES / name).read_text())


def test_priya_reconciliation():
    out = reconcile_itc(_load("books_purchases_q2_2026.json"),
                        _load("gstr2b_q2_2026.json"))
    s = out["summary"]
    assert s["books_itc_total"] == 2400 + 1620 + 1080 + 2160
    assert s["gstr2b_itc_total"] == 2640 + 1620 + 1080
    assert s["matched_count"] == 2
    assert s["mismatched_count"] == 1
    assert s["only_in_books_count"] == 1
    assert s["only_in_2b_count"] == 0
    assert s["claimable_itc"] == 1620
    assert s["blocked_itc"] == 1080
    assert "mismatch" in s["recommendation"].lower()


def test_blocked_reason_is_reported():
    out = reconcile_itc(_load("books_purchases_q2_2026.json"),
                        _load("gstr2b_q2_2026.json"))
    blocked_rows = [r for r in out["matched"] if not r["itc_allowed"]]
    assert len(blocked_rows) == 1
    assert "17(5)(b)" in blocked_rows[0]["blocked_itc"]


def test_clean_reconciliation_passes():
    row = {"supplier_gstin": "27ABCDE1234F1Z0", "invoice_number": "X1",
           "invoice_date": "2026-08-01", "taxable_value": 1000,
           "itc_amount": 90, "hsn_sac": "4821"}
    out = reconcile_itc([row], [row])
    assert out["summary"]["claimable_itc"] == 90
    assert out["summary"]["recommendation"].startswith("ITC agrees")
