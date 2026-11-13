import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gst_mcp.core.itr_crossover import (compute_tax, itr_advance_tax_estimate,
                                        itr_turnover_reconcile, presumptive_check)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "priya_pickles"


def test_new_regime_slabs():
    out = compute_tax(1_650_000, "new")
    assert out["taxable_income"] == 1_575_000
    assert out["base_tax"] == 116250
    assert out["total_tax"] == 120900


def test_new_regime_rebate_makes_low_income_nil():
    out = compute_tax(9_00_000, "new")
    assert out["total_tax"] == 0


def test_old_regime_slabs():
    out = compute_tax(1_650_000, "old")
    assert out["total_tax"] == 304200


def test_advance_tax_instalments():
    out = itr_advance_tax_estimate(1_650_000, "new")
    amounts = [i["cumulative_amount"] for i in out["instalments"]]
    assert amounts == [18135, 54405, 90675, 120900]


def test_turnover_reconcile_flags_variance():
    data = json.loads((FIXTURES / "itr_fy2025_26.json").read_text())
    out = itr_turnover_reconcile(data["gstr3b_annual_turnover"],
                                 data["itr_gross_receipts"],
                                 data["itr_presumptive_scheme"])
    assert out["difference"] == 230000
    assert out["difference_pct"] == 5.5
    assert out["in_sync"] is False
    assert any("ITR turnover higher" in f for f in out["flags"])


def test_presumptive_check():
    out = presumptive_check(4_180_000, "44AD", 0.96)
    assert out["eligible"] is True
    assert out["limit"] == 3_00_00_000
    out2 = presumptive_check(4_180_000, "44AD", 0.6)
    assert out2["limit"] == 2_00_00_000
    assert out2["eligible"] is True


def test_new_regime_87a_marginal_relief():
    # s.87A marginal relief: taxable Rs 12,05,000 -> tax limited to Rs 5,000, + 4% cess = 5,200.
    out = compute_tax(12_80_000, "new")
    assert out["base_tax"] == 5000
    assert out["total_tax"] == 5200
    # Rs 12L taxable still gets the full rebate; far above 12L the relief does not bind.
    assert compute_tax(12_75_000, "new")["total_tax"] == 0
    assert compute_tax(18_00_000, "new")["total_tax"] == 150800
