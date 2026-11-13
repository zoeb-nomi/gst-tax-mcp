import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gst_mcp.core.deadlines import filing_deadlines


def test_monthly_deadlines():
    out = filing_deadlines("2026-10", "monthly")
    due = {d["form"]: d["due_date"] for d in out}
    assert due["GSTR-1"] == "2026-11-11"
    assert due["GSTR-3B"] == "2026-11-20"


def test_qrdp_quarter_maharashtra():
    out = filing_deadlines("2026-Q2", "qrdp", state_code="27")
    due = {d["form"]: d["due_date"] for d in out}
    assert due["GSTR-1"] == "2026-10-13"
    assert due["GSTR-3B"] == "2026-10-22"
    assert due["PMT-06"] == "2026-10-25"


def test_qrdp_quarter_state_groups():
    # Rule 61(1)(ii): Tamil Nadu is in the 22nd-day group, Delhi in the 24th-day group.
    for state, day in (("33", "2026-10-22"), ("32", "2026-10-22"), ("07", "2026-10-24")):
        out = filing_deadlines("2026-Q2", "qrdp", state_code=state)
        due = {d["form"]: d["due_date"] for d in out}
        assert due["GSTR-3B"] == day


def test_iff_only_months_1_and_2():
    # Rule 59(2): IFF for months 1 and 2 of a quarter only; month 3 has none.
    for period, due in (("2026-10", "2026-11-13"), ("2026-11", "2026-12-13")):
        out = filing_deadlines(period, "qrdp")
        assert any(d["form"].startswith("GSTR-1 IFF") and d["due_date"] == due for d in out)
    out = filing_deadlines("2026-12", "qrdp")
    assert not any(d["form"].startswith("GSTR-1 IFF") for d in out)


def test_composition_quarter():
    out = filing_deadlines("2026-Q2", "composition")
    assert out[0]["form"] == "CMP-08"
    assert out[0]["due_date"] == "2026-10-18"


def test_fy_annual_and_itr():
    out = filing_deadlines("FY2026-27", "monthly")
    due = {d["form"]: d["due_date"] for d in out}
    assert due["GSTR-9"] == "2027-12-31"
    assert due["ITR-3/4 (non-audit)"] == "2027-07-31"
    assert due["ITR-3/5/6 (audit)"] == "2027-10-31"


def test_qrmp_alias_matches_qrdp():
    # QRMP is the official name; a model passing it must not get monthly dates.
    assert filing_deadlines("2026-Q2", "qrmp", "32") == filing_deadlines("2026-Q2", "qrdp", "32")


def test_unknown_filer_type_is_an_error():
    import pytest
    with pytest.raises(ValueError):
        filing_deadlines("2026-Q2", "quartely", "32")
