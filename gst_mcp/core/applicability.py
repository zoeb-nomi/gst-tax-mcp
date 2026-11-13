"""GST registration applicability logic."""
from __future__ import annotations

from .data import (CITE_ECO_2023, CITE_S10_1, CITE_S10_2A, COMPOSITION_75L_STATES,
                   COMPOSITION_RATES, GOODS_THRESHOLD_20L_STATES, S10_1_SERVICES_ALLOWANCE,
                   S10_2A, S10_2A_EXCLUDED_GOODS, SERVICES_THRESHOLD_10L_STATES, THRESHOLDS)


def check_applicability(profile: dict) -> dict:
    """Determine whether a business must register under GST and its options.

    profile keys:
      aggregate_turnover_prior_fy (float, rupees)
      state_code (2-char GST state code)
      supplies_goods (bool), supplies_services (bool)
      inter_state_supply (bool), sells_via_ecommerce (bool)
      casual_taxable_person (bool)
      composition_scheme_interest (bool)
    optional, used for the composition answer:
      services_turnover_prior_fy (float): value of services other than restaurant
        service in the preceding FY; decides s.10(1) vs s.10(2A) for a mixed supplier
      supplies_restaurant_service (bool): restaurant / outdoor catering (Sch II 6(b))
      supplies_services_via_ecommerce (bool); makes_exempt_supplies (bool, interest
        on deposits/loans does not count); non_resident_taxable_person (bool)
      goods_hsn (list of HSN codes supplied)
    """
    turnover = float(profile.get("aggregate_turnover_prior_fy", 0) or 0)
    state = str(profile.get("state_code", "27"))
    goods = bool(profile.get("supplies_goods", False))
    services = bool(profile.get("supplies_services", False))
    inter_state = bool(profile.get("inter_state_supply", False))
    ecommerce = bool(profile.get("sells_via_ecommerce", False))
    casual = bool(profile.get("casual_taxable_person", False))
    wants_composition = bool(profile.get("composition_scheme_interest", False))
    # Thresholds differ by supply type and by State (Notif 10/2019-CT for goods;
    # services Rs 10L only in Manipur, Mizoram, Nagaland, Tripura). See data.py.
    goods_special = state in GOODS_THRESHOLD_20L_STATES
    services_special = state in SERVICES_THRESHOLD_10L_STATES
    special = goods_special or services_special

    compulsory = []
    if casual:
        compulsory.append("Casual taxable persons must register regardless of turnover")
    if inter_state and goods:
        compulsory.append("Inter-state supply of goods makes registration compulsory at any turnover")
    if ecommerce and goods:
        compulsory.append("Supply of goods through an e-commerce operator requires registration "
                          "regardless of threshold")

    goods_limit = THRESHOLDS["goods_special"] if goods_special else THRESHOLDS["goods_normal"]
    services_limit = (THRESHOLDS["services_special"] if services_special
                      else THRESHOLDS["services_normal"])
    over_goods = goods and turnover > goods_limit
    over_services = services and turnover > services_limit
    if over_goods:
        compulsory.append(f"Goods turnover Rs {turnover:,.0f} exceeds the "
                          f"{'reduced' if goods_special else 'standard'} goods threshold of "
                          f"Rs {goods_limit:,}")
    if over_services:
        compulsory.append(f"Services turnover Rs {turnover:,.0f} exceeds the "
                          f"{'reduced' if services_special else 'standard'} services threshold of "
                          f"Rs {services_limit:,}")

    mandatory = bool(compulsory)
    info = []
    info.append(f"State {state}: goods threshold Rs {goods_limit:,}, services threshold Rs {services_limit:,}")
    if not mandatory:
        info.append("Aggregate turnover is below the applicable threshold; registration is voluntary")

    comp = _composition(profile, turnover, state, goods, services, inter_state, ecommerce, casual)
    composition_notes = comp["notes"] if wants_composition else []
    comp_eligible = wants_composition and comp["eligible"]
    return {
        "needs_registration": mandatory,
        "threshold_goods": goods_limit,
        "threshold_services": services_limit,
        "special_category_state": special,
        "reasons": compulsory + info,
        "composition_eligible": comp_eligible,
        "composition_notes": composition_notes,
        "composition_path": comp["path"] if wants_composition else None,
        "composition_limit": comp["limit"] if wants_composition else None,
        "composition_rate": comp["rate"] if wants_composition else None,
        "composition_rules": comp["rules"] if wants_composition else [],
        "einvoice_mandatory": turnover > THRESHOLDS["einvoice_ato"],
        "einvoice_mandatory_ato": THRESHOLDS["einvoice_ato"],
        "qrdp_eligible": turnover <= THRESHOLDS["qrdp_ato"],
        "recommended_filer_type": "qrdp" if turnover <= THRESHOLDS["qrdp_ato"] else "monthly",
    }


def _rule(rule: str, ok: bool | None, cite: str) -> dict:
    return {"rule": rule, "result": "pass" if ok else ("fail" if ok is False else "not_checked"),
            "citation": cite}


def _composition(profile: dict, turnover: float, state: str, goods: bool, services: bool,
                 inter_state: bool, ecommerce: bool, casual: bool) -> dict:
    """Pick the composition route and test every condition of it.

    s.10(1): goods suppliers, manufacturers and restaurants, plus other services
    up to the allowance. s.10(2A): anyone shut out of s.10(1) by the services
    allowance, turnover up to Rs 50L, 6% (Notif 2/2019-CT(Rate)).
    """
    restaurant = bool(profile.get("supplies_restaurant_service", False))
    # A restaurant with no other services given has nothing to count against the allowance.
    other_services = services and not (restaurant and not profile.get("services_turnover_prior_fy"))
    svc_raw = profile.get("services_turnover_prior_fy")
    svc_turnover = float(svc_raw) if svc_raw not in (None, "") else None
    exempt = bool(profile.get("makes_exempt_supplies", False))
    nrtp = bool(profile.get("non_resident_taxable_person", False))
    svc_eco = bool(profile.get("supplies_services_via_ecommerce", False)) or (ecommerce and services and not goods)
    hsns = [str(h).replace(" ", "").replace(".", "") for h in (profile.get("goods_hsn") or [])]
    notes: list[str] = []

    allowance = max(S10_1_SERVICES_ALLOWANCE["share"] * turnover, S10_1_SERVICES_ALLOWANCE["floor"])
    if not other_services:
        services_fit_10_1 = True
    elif not goods and not restaurant:
        services_fit_10_1 = False          # a pure service provider: s.10(1) is closed
    elif svc_turnover is not None:
        services_fit_10_1 = svc_turnover <= allowance
    else:
        services_fit_10_1 = None           # mixed supplier, split unknown

    comp_75 = state in COMPOSITION_75L_STATES
    limit_10_1 = THRESHOLDS["composition_limit_special"] if comp_75 else THRESHOLDS["composition_limit"]

    common = [
        _rule("No supplies of goods or services not leviable to tax; interest on deposits/loans is ignored",
              not exempt, "s.10(2)(b) / s.10(2A)(a); Notif 2/2019-CT(Rate) cond. 1(iii) and para 2"),
        _rule("No inter-State outward supply of goods or services", not inter_state,
              "s.10(2)(c) / s.10(2A)(b); Notif 2/2019-CT(Rate) cond. 1(iv)"),
        _rule("No supply of services through an e-commerce operator that collects TCS (s.52)",
              not svc_eco, CITE_ECO_2023 + "; Notif 2/2019-CT(Rate) cond. 1(vi)"),
        _rule("Not a casual or non-resident taxable person", not (casual or nrtp),
              "s.10(2)(f) / s.10(2A)(e); Notif 2/2019-CT(Rate) cond. 1(v)"),
    ]

    if services_fit_10_1 is False:
        path = "s10_2A"
        excluded = [g for g in S10_2A_EXCLUDED_GOODS if any(h.startswith(g["prefix"]) for h in hsns)]
        rules = [
            _rule(f"Services beyond the s.10(1) allowance (higher of 10% of turnover or Rs 5 lakh), "
                  f"so s.10(1) is not available and s.10(2A) applies",
                  True, "CGST Act s.10(1) second proviso; s.10(2A)"),
            _rule(f"Aggregate turnover in the preceding FY at most Rs {S10_2A['limit']:,} "
                  f"(same limit in every State)", turnover <= S10_2A["limit"],
                  "s.10(2A); Notif 2/2019-CT(Rate) cond. 1(i)"),
            *common,
            _rule("Does not supply ice cream (2105), pan masala (2106 90 20) or tobacco (Ch. 24)",
                  (not excluded) if hsns else (True if not goods else None),
                  "s.10(2A)(d); Notif 2/2019-CT(Rate) cond. 1(vii) and Annexure"),
        ]
        rate = {"cgst": S10_2A["cgst"], "sgst_utgst": S10_2A["sgst"],
                "total": S10_2A["cgst"] + S10_2A["sgst"], "citation": CITE_S10_2A}
        notes.append(f"Service provider: composition is the s.10(2A) scheme, limit Rs {S10_2A['limit']:,} "
                     f"turnover in the preceding FY, tax 6% (3% CGST + 3% SGST) "
                     f"(Notif 2/2019-CT(Rate))")
        if excluded:
            notes.append("Supplies notified goods excluded from the 6% scheme: "
                         + ", ".join(g["desc"] for g in excluded))
        if not hsns and goods:
            notes.append("Goods codes not given: confirm none are ice cream, pan masala or tobacco")
        notes.append("Bill of supply, not tax invoice; no tax collected from customers; no input tax credit; "
                     "reverse-charge tax still paid at normal rates (Notif 2/2019-CT(Rate) cond. 3-7)")
    else:
        path = "s10_1" if services_fit_10_1 else "undetermined"
        r = (COMPOSITION_RATES["restaurant"] if restaurant and not goods
             else COMPOSITION_RATES["trader_manufacturer"])
        rules = [
            _rule(f"Services other than restaurant service within the s.10(1) allowance "
                  f"(here Rs {allowance:,.0f})", services_fit_10_1, "CGST Act s.10(1) second proviso"),
            _rule(f"Aggregate turnover in the preceding FY at most Rs {limit_10_1:,} "
                  f"({'reduced-limit State' if comp_75 else 'standard'})", turnover <= limit_10_1,
                  "s.10(1); Notif 14/2019-CT"),
            *common,
        ]
        notified = [g for g in S10_2A_EXCLUDED_GOODS if any(h.startswith(g["prefix"]) for h in hsns)]
        if notified:
            mfr = profile.get("manufactures_goods")
            rules.append(_rule("Not a manufacturer of goods notified under s.10(2)(e): "
                               + ", ".join(g["desc"] for g in notified),
                               None if mfr is None else not bool(mfr),
                               "s.10(2)(e); Notif 14/2019-CT para (ii)"))
            if mfr is None:
                notes.append("Notified goods in the HSN list: s.10(1) is barred if you manufacture them "
                             "(trading them is fine); set manufactures_goods to decide")
        notes.append("s.10(2)(e) also bars manufacturers of other goods notified in Notif 14/2019-CT "
                     "(e.g. aerated waters); this tool checks ice cream, pan masala and tobacco only")
        rate = {"cgst": r / 2, "sgst_utgst": r / 2, "total": r, "citation": CITE_S10_1}
        notes.append(f"Composition turnover limit: Rs {limit_10_1:,} "
                     f"({'reduced-limit State' if comp_75 else 'standard'})")
        if path == "undetermined":
            notes.append("Supplies goods and services but services_turnover_prior_fy was not given: "
                         f"s.10(1) applies if services are within Rs {allowance:,.0f}, otherwise the "
                         f"6% s.10(2A) scheme with a Rs {S10_2A['limit']:,} limit")

    # Failure notes, in the wording the earlier versions used.
    for row in rules:
        if row["result"] == "fail":
            if "turnover in the preceding FY" in row["rule"]:
                notes.append("Turnover exceeds the composition limit")
            elif "inter-State" in row["rule"]:
                notes.append("Composition suppliers cannot make inter-state supply of goods or services")
            else:
                notes.append("Not eligible: " + row["rule"].lower())
    eligible = all(r["result"] != "fail" for r in rules)
    if path == "undetermined":
        # Either route works only if the stricter s.10(2A) conditions also hold.
        eligible = eligible and turnover <= S10_2A["limit"]
        if not eligible and turnover > S10_2A["limit"] and turnover <= limit_10_1:
            notes.append("Give the services turnover: above Rs 50 lakh only s.10(1) is possible")
    if goods and ecommerce:
        notes.append("Goods through an e-commerce operator no longer bar composition from 1 Oct 2023 "
                     f"({CITE_ECO_2023}); the operator's own conditions still apply")
    if services:
        notes.append("Same PAN: every registration under the PAN must be in the same scheme "
                     "(s.10(2) proviso; Notif 2/2019-CT(Rate) cond. 2)")
    if path == "s10_2A" and goods and ecommerce:
        notes.append("Goods through an e-commerce operator: s.10(2A)(c) now bars only services, but "
                     "condition 1(vi) of Notif 2/2019-CT(Rate) as issued bars any supply; check the "
                     "current text before opting")
    limit = S10_2A["limit"] if path == "s10_2A" else limit_10_1
    return {"path": path, "eligible": eligible, "limit": limit, "rate": rate, "rules": rules,
            "notes": notes}
