"""Deterministic filing session for the public demo video.

Drives the same nine MCP tools the LangGraph agent exposes, in a fixed
order, against the Priya's Homemade Pickles fixtures. The transcript feeds
the public demo video; `gst_mcp/agent.py` shows the same flow driven by an
LLM.
"""
from __future__ import annotations

import json
from pathlib import Path

from session_mcp import ROOT, Session, money

FX = ROOT / "fixtures" / "priya_pickles"


def say_savings(s: Session, text: str) -> None:
    s.say(f"# {text}")


async def steps(s: Session, session) -> None:
    profile = json.loads((FX / "profile.json").read_text())
    s.say("== Step 0 · the client ==")
    s.say(f"# {profile['business_name']}, {profile['constitution']} in {profile['state']}")
    s.say(f"# prior-FY turnover {money(profile['aggregate_turnover_prior_fy'])}, "
          f"goods, sells to Karnataka (inter-state)")
    s.say()
    s.say("== Step 1 · is GST registration required? ==")
    out = await s.call(session, "gst_applicability", {"profile": str(FX / "profile.json")},
                       keep=["needs_registration", "composition_eligible",
                             "recommended_filer_type", "reasons", "composition_notes"])
    say_savings(s, f"Registration: {'required' if out['needs_registration'] else 'not required'}; "
                  f"composition scheme: {'available' if out['composition_eligible'] else 'not available'} "
                  f"(inter-state goods supply blocks it); filer type: {out['recommended_filer_type']}")
    s.say()

    s.say("== Step 2 · when must this quarter be filed? ==")
    await s.call(session, "gst_filing_deadlines",
                 {"period": "2026-Q2", "filer_type": out["recommended_filer_type"],
                  "state_code": "27"},
                 keep=["deadlines"])
    say_savings(s, "Q2 (Jul-Sep 2026): GSTR-1 by 13 Oct 2026, GSTR-3B by 22 Oct 2026 "
                   "(Maharashtra QRDP category X), tax challan by 25 Oct 2026")
    s.say()

    s.say("== Step 3 · reverse-charge freight (GTA) ==")
    freight = {"lines": [{"description": "Freight (GTA) under reverse charge",
                          "hsn_sac": "996411", "quantity": 1, "unit_price": 8000,
                          "place_of_supply_state": "27", "supplier_state": "27",
                          "reverse_charge": True}]}
    await s.call(session, "calc_gst_liability", {"invoice": json.dumps(freight)},
                 keep=["lines", "totals"])
    say_savings(s, "Rs 400 self-assessed under reverse charge - paid in cash, then "
                   "claimed as ITC in the same return (net nil, but it must be reported)")
    s.say()

    s.say("== Step 4 · ITC: books vs GSTR-2B ==")
    await s.call(session, "reconcile_itc_tool",
                 {"books": str(FX / "books_purchases_q2_2026.json"),
                  "gstr2b": str(FX / "gstr2b_q2_2026.json")},
                 keep=["summary"])
    say_savings(s, "Claim only Rs 1,620 now. Rs 1,080 catering credit is blocked under "
                   "section 17(5)(b); Rs 2,160 invoice is missing from 2B - chase the supplier; "
                   "Rs 400 difference on the jar vendor needs reconciliation")
    s.say()

    s.say("== Step 5 · GSTR-1 summary ==")
    await s.call(session, "gstr1_summary_tool",
                 {"invoices": str(FX / "outward_invoices_q2_2026.json")},
                 keep=["tables", "totals_excl_hsn"])
    say_savings(s, "Rs 6,99,600 taxable, Rs 25,980 tax net of the credit note. "
                   "B2C-large (5A) catches the Rs 3.2 lakh Bengaluru order that would "
                   "otherwise hide in B2C-small")
    s.say()

    s.say("== Step 6 · e-invoice check on the Meridian order ==")
    await s.call(session, "validate_einvoice_tool",
                 {"einvoice": str(FX / "einvoice_meridian.json"),
                  "supplier_ato": profile["aggregate_turnover_prior_fy"]},
                 keep=["valid", "errors", "warnings", "hsn_digits_required"])
    say_savings(s, "E-invoicing is not mandatory below Rs 5 crore turnover, but the "
                   "buyer's AP team asked for an e-invoice-ready bill: valid")
    s.say()

    s.say("== Step 7 · ITR crossover ==")
    itr = json.loads((FX / "itr_fy2025_26.json").read_text())
    await s.call(session, "itr_turnover_reconcile_tool",
                 {"gstr3b_turnover": itr["gstr3b_annual_turnover"],
                  "itr_gross_receipts": itr["itr_gross_receipts"],
                  "itr_presumptive_scheme": itr["itr_presumptive_scheme"]},
                 keep=["difference", "difference_pct", "in_sync", "flags"])
    say_savings(s, "ITR shows Rs 2,30,000 (5.5%) more than GST turnover - above the 5% "
                   "band the department's comparators use; explain or amend before the notice")
    s.say()

    s.say("== Step 8 · advance-tax estimate for next year ==")
    await s.call(session, "itr_advance_tax_estimate_tool",
                 {"annual_income_projection": itr["projected_income_fy2026_27"],
                  "regime": "new"},
                 keep=["annual_tax", "instalments", "regime_comparison"])
    say_savings(s, "Projected Rs 16.5 lakh income: Rs 1,20,900 tax, four instalments - "
                   "15 June / 15 Sep / 15 Dec / 15 Mar")
    s.say()

    s.say("== Filing pack ==")
    s.say("# GSTR-1: Rs 6,99,600 taxable, tax Rs 25,980 (net of credit note)")
    s.say("# GSTR-3B: outward tax Rs 25,980 + RCM Rs 400; ITC claim Rs 1,620 now")
    s.say("# Cash to pay by 25 Oct 2026: Rs 24,760 (liability less ITC, incl. RCM)")
    s.say("# Flags: blocked ITC 1,080; mismatch 400; missing-in-2B 2,160; ITR variance 5.5%")


def main() -> None:
    s = Session("Priya's Homemade Pickles - Q2 2026 GST filing session")
    lines = s.run(steps)
    out = Path(__file__).resolve().parent / "transcripts" / "filing_session.txt"
    s.save(out)
    print(f"transcript: {out} ({len(lines)} lines)")


if __name__ == "__main__":
    main()
