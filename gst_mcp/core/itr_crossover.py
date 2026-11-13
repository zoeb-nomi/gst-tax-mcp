"""ITR crossover tools: turnover reconciliation and advance-tax estimation."""
from __future__ import annotations


def _new_regime_tax(taxable: float) -> float:
    slabs = [(4_00_000, 0.0), (8_00_000, 5.0), (12_00_000, 10.0), (16_00_000, 15.0),
             (20_00_000, 20.0), (24_00_000, 25.0), (float("inf"), 30.0)]
    tax = _slab_tax(taxable, slabs, rebate_limit=12_00_000, rebate_amount=60_000)
    if taxable > 12_00_000:
        # s.87A marginal relief (new regime, FY 2025-26): tax is capped at the income
        # above Rs 12L, so nobody pays more tax than the rise in income. Cess is on top.
        tax = min(tax, taxable - 12_00_000)
    return tax


def _old_regime_tax(taxable: float) -> float:
    slabs = [(2_50_000, 0.0), (5_00_000, 5.0), (10_00_000, 20.0), (float("inf"), 30.0)]
    return _slab_tax(taxable, slabs, rebate_limit=5_00_000, rebate_amount=12_500)


def _slab_tax(taxable: float, slabs, rebate_limit: float, rebate_amount: float) -> float:
    tax, prev = 0.0, 0.0
    for cap, rate in slabs:
        if taxable > prev:
            tax += (min(taxable, cap) - prev) * rate / 100
            prev = cap
        else:
            break
    if taxable <= rebate_limit:
        tax = max(0.0, tax - rebate_amount)
    return tax


def compute_tax(annual_income: float, regime: str = "new") -> dict:
    """Total tax on projected annual income under a regime (salaried-style slabs)."""
    taxable = max(0.0, float(annual_income))
    std_deduction = 75_000 if regime == "new" else 50_000
    taxable = max(0.0, taxable - std_deduction)
    base = _new_regime_tax(taxable) if regime == "new" else _old_regime_tax(taxable)
    cess = round(base * 0.04, 2)
    return {"taxable_income": taxable, "std_deduction": std_deduction,
            "regime": regime, "base_tax": round(base, 2), "cess_4pc": cess,
            "total_tax": round(base + cess, 2)}


def itr_turnover_reconcile(gstr3b_turnover: float, itr_gross_receipts: float,
                           itr_presumptive_scheme: str = "none") -> dict:
    """Reconcile GST turnover with the ITR-reported turnover.

    Mismatches between GSTR-3B/9 turnover and ITR gross receipts are a common
    notice trigger (itc-verifier / AIS comparison).
    """
    g = float(gstr3b_turnover or 0)
    i = float(itr_gross_receipts or 0)
    diff = round(i - g, 2)
    pct = round(diff / g * 100, 2) if g else (100.0 if i else 0.0)
    flags = []
    if abs(pct) > 5:
        flags.append(f"Turnover differs by {pct}% (Rs {diff:,.0f}); "
                     f"the ITC reconciliation statement expects ITR >= GSTR turnover "
                     f"and flags variances beyond ~5%")
    if itr_presumptive_scheme == "44AD" and i > 3_00_00_000:
        flags.append("Turnover exceeds the Rs 3 crore presumptive limit (44AD, "
                     ">=95% digital receipts); books and audit apply")
    if itr_presumptive_scheme == "44ADA" and i > 75_00_000:
        flags.append("Receipts exceed the Rs 75 lakh presumptive limit (44ADA, "
                     ">=95% digital receipts)")
    if diff > 0:
        flags.append("ITR turnover higher than GST turnover: GST-registered supplies "
                     "may be missing from returns, or exempt/nil-rate receipts explain it")
    if diff < 0:
        flags.append("GST turnover higher than ITR turnover: check for ITR filing "
                     "gaps, credit notes after year-end, or misclassification")
    return {"gstr3b_turnover": g, "itr_gross_receipts": i, "difference": diff,
            "difference_pct": pct, "in_sync": abs(pct) <= 5,
            "flags": flags or ["Turnover agrees within 5%"]}


def itr_advance_tax_estimate(annual_income_projection: float, regime: str = "new") -> dict:
    """Estimate advance-tax instalments from projected annual income."""
    from .deadlines import advance_tax_schedule
    return advance_tax_schedule(annual_income_projection, regime)


def presumptive_check(turnover: float, scheme: str = "44AD",
                      digital_receipt_share: float = 1.0) -> dict:
    """Check presumptive-taxation eligibility against the current limits."""
    limits = {"44AD": (3_00_00_000 if digital_receipt_share >= 0.95 else 2_00_00_000,
                      "business, 6%/8% deemed profit"),
              "44ADA": (75_00_000 if digital_receipt_share >= 0.95 else 50_00_000,
                        "profession, 50% deemed profit")}
    limit, desc = limits.get(scheme, (0, "unknown scheme"))
    eligible = 0 < turnover <= limit
    return {"scheme": scheme, "turnover": turnover,
            "limit": limit, "description": desc,
            "eligible": eligible,
            "note": ("" if eligible else
                     "Turnover above the limit: regular books, tax audit if "
                     "turnover > Rs 1 crore (or Rs 10 crore with 95%+ digital "
                     "transactions)")}
