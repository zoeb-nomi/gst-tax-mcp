import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gst_mcp.core.applicability import check_applicability

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "priya_pickles"


def test_priya_must_register_not_composition():
    profile = __import__("json").loads((FIXTURES / "profile.json").read_text())
    out = check_applicability(profile)
    assert out["needs_registration"] is True
    assert out["composition_eligible"] is False
    assert any("inter-state" in r.lower() for r in out["composition_notes"])
    assert out["qrdp_eligible"] is True
    assert out["einvoice_mandatory_ato"] == 5_00_00_000


def test_small_services_business_below_threshold():
    out = check_applicability({"aggregate_turnover_prior_fy": 900_000,
                               "state_code": "27", "supplies_services": True})
    assert out["needs_registration"] is False


def test_special_state_thresholds():
    # Notif 10/2019-CT: goods limit is Rs 20L in the ten listed States (incl. Arunachal),
    # Rs 40L elsewhere including Assam. Services Rs 10L only in Manipur/Mizoram/Nagaland/Tripura.
    out = check_applicability({"aggregate_turnover_prior_fy": 25_00_000,
                               "state_code": "12", "supplies_goods": True})
    assert out["needs_registration"] is True
    assert out["threshold_goods"] == 20_00_000
    out2 = check_applicability({"aggregate_turnover_prior_fy": 30_00_000,
                                "state_code": "18", "supplies_goods": True})
    assert out2["needs_registration"] is False
    assert out2["threshold_goods"] == 40_00_000
    out3 = check_applicability({"aggregate_turnover_prior_fy": 15_00_000,
                                "state_code": "05", "supplies_services": True})
    assert out3["needs_registration"] is False
    assert out3["threshold_services"] == 20_00_000
    out4 = check_applicability({"aggregate_turnover_prior_fy": 15_00_000,
                                "state_code": "16", "supplies_services": True})
    assert out4["needs_registration"] is True


def test_casual_taxable_person_always_registers():
    out = check_applicability({"aggregate_turnover_prior_fy": 100_000,
                               "state_code": "27", "casual_taxable_person": True})
    assert out["needs_registration"] is True


def _svc(turnover, **kw):
    p = {"aggregate_turnover_prior_fy": turnover, "state_code": "27", "supplies_services": True,
         "composition_scheme_interest": True}
    p.update(kw)
    return check_applicability(p)


def test_service_provider_gets_s10_2A_not_goods_limit():
    out = _svc(30_00_000)
    assert out["composition_path"] == "s10_2A"
    assert out["composition_eligible"] is True
    assert out["composition_limit"] == 50_00_000
    assert out["composition_rate"]["cgst"] == 3.0 and out["composition_rate"]["total"] == 6.0
    assert not any("1,50,00,000" in n or "15,000,000" in n for n in out["composition_notes"])
    assert all(r["citation"] for r in out["composition_rules"])
    assert any("2/2019" in r["citation"] for r in out["composition_rules"])


def test_s10_2A_limit_is_50_lakh_even_in_reduced_limit_state():
    assert _svc(60_00_000, state_code="11")["composition_eligible"] is False
    assert _svc(45_00_000, state_code="11")["composition_limit"] == 50_00_000


def test_s10_2A_exclusions():
    assert _svc(30_00_000, inter_state_supply=True)["composition_eligible"] is False
    assert _svc(30_00_000, sells_via_ecommerce=True)["composition_eligible"] is False
    assert _svc(30_00_000, makes_exempt_supplies=True)["composition_eligible"] is False
    assert _svc(30_00_000, non_resident_taxable_person=True)["composition_eligible"] is False
    out = _svc(40_00_000, supplies_goods=True, services_turnover_prior_fy=20_00_000,
               goods_hsn=["2402 20 90"])
    assert out["composition_path"] == "s10_2A" and out["composition_eligible"] is False


def test_mixed_supplier_within_allowance_stays_s10_1():
    out = _svc(44_50_000, supplies_goods=True, services_turnover_prior_fy=4_50_000)
    assert out["composition_path"] == "s10_1"
    assert out["composition_rate"]["total"] == 1.0
    out = _svc(1_00_00_000, supplies_goods=True, services_turnover_prior_fy=9_00_000)
    assert out["composition_path"] == "s10_1" and out["composition_eligible"] is True


def test_mixed_supplier_without_split_is_flagged():
    out = _svc(30_00_000, supplies_goods=True)
    assert out["composition_path"] == "undetermined"
    assert any("services_turnover_prior_fy" in n for n in out["composition_notes"])


def test_restaurant_stays_s10_1_at_5_percent():
    out = _svc(80_00_000, supplies_restaurant_service=True)
    assert out["composition_path"] == "s10_1"
    assert out["composition_rate"]["total"] == 5.0
    assert out["composition_eligible"] is True


def test_goods_via_ecommerce_no_longer_bars_s10_1():
    out = check_applicability({"aggregate_turnover_prior_fy": 30_00_000, "state_code": "27",
                               "supplies_goods": True, "sells_via_ecommerce": True,
                               "composition_scheme_interest": True})
    assert out["composition_path"] == "s10_1" and out["composition_eligible"] is True


def test_s10_1_bars_manufacturer_of_notified_goods():
    # s.10(2)(e): a manufacturer of ice cream is barred from s.10(1); a trader of it is not.
    base = {"aggregate_turnover_prior_fy": 80_00_000, "state_code": "27", "supplies_goods": True,
            "composition_scheme_interest": True, "goods_hsn": ["2105 00 00"]}
    assert check_applicability({**base, "manufactures_goods": True})["composition_eligible"] is False
    assert check_applicability({**base, "manufactures_goods": False})["composition_eligible"] is True
    out = check_applicability(base)
    assert any("manufactures_goods" in n for n in out["composition_notes"])
