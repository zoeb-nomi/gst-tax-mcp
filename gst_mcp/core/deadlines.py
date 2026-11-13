"""Filing deadlines: GSTR-1/3B (monthly and QRDP), composition, annual, ITR."""
from __future__ import annotations

import calendar
from datetime import date

from .data import ADVANCE_TAX_INSTALLMENTS, DEADLINE_OVERRIDES, DEADLINE_RULES


def _advance(year: int, month: int, day: int) -> date:
    last = calendar.monthrange(year, month)[1]
    return date(year, month, min(day, last))


def _shift(year: int, month: int, months: int) -> tuple[int, int]:
    total = (year * 12 + (month - 1)) + months
    return total // 12, total % 12 + 1


def filing_deadlines(period: str, filer_type: str = "monthly",
                     state_code: str = "27", turnover_above_5cr: bool = False) -> list[dict]:
    """Return the due dates that apply to a filing period.

    period: "YYYY-MM" for monthly/IFF periods, "YYYY-Q1".."YYYY-Q4" for
    Indian fiscal quarters (Q1 = April-June of the given year), or
    "FY2026-27" (annual + ITR).
    filer_type: "monthly", "qrdp" (QRMP; "qrmp" is accepted too), "composition".
    """
    filer_type = _normalise_filer_type(filer_type)
    results: list[dict] = []
    if period.startswith("FY"):
        year = int(period[2:6])
        for form, d in (("GSTR-9", (year + 1, 12, 31)), ("GSTR-9C", (year + 1, 12, 31)),
                        ("GSTR-4", (year + 1, 6, 30))):
            results.append(_entry(form, "annual", date(*d), period))
        for form, d in (("ITR-3/4 (non-audit)", (year + 1, 7, 31)),
                        ("ITR-3/5/6 (audit)", (year + 1, 10, 31))):
            results.append(_entry(form, "itr", date(*d), period))
        return results

    if "-Q" in period:
        year, q = period.split("-Q")
        year = int(year)
        qstart_year, qstart_month = _shift(year, 4, 3 * (int(q) - 1))
        after_year, after_month = _shift(qstart_year, qstart_month, 3)
        base = f"{after_year}-{after_month:02d}"
        if filer_type == "composition":
            results.append(_entry("CMP-08", "composition", _advance(after_year, after_month, 18), period))
            return results
        if filer_type == "qrdp" and not turnover_above_5cr:
            results.append(_entry("GSTR-1", "qrdp_quarter", _advance(after_year, after_month, 13), period))
            cat = "qrdp_quarter_catX" if state_code in _QRMP_22ND else "qrdp_quarter_catXp"
            results.append(_entry("GSTR-3B", cat, _advance(after_year, after_month, 22 if cat.endswith("X") else 24), period))
            results.append(_entry("PMT-06", "qrdp_quarter", _advance(after_year, after_month, 25), period))
        else:
            results.append(_entry("GSTR-1", "monthly", _advance(after_year, after_month, 11), period))
            results.append(_entry("GSTR-3B", "monthly", _advance(after_year, after_month, 20), period))
        return results

    year, month = (int(x) for x in period.split("-"))
    after_year, after_month = _shift(year, month, 1)
    if filer_type == "composition":
        results.append(_entry("GSTR-4 (not due monthly; CMP-08 is quarterly)", "composition",
                              _advance(year, month, calendar.monthrange(year, month)[1]), period))
        return results
    if filer_type == "qrdp" and not turnover_above_5cr:
        # Rule 59(2): IFF is available for months 1 and 2 of a quarter only, by the 13th
        # of the next month. Month 3 is reported in the quarterly GSTR-1.
        quarter_month = (month - 1) % 3
        if quarter_month == 2:
            results.append(_note_entry("GSTR-1", "Month 3 of the quarter: no IFF (Rule 59(2)); "
                                       "report in the quarterly GSTR-1 due on the 13th after "
                                       "quarter end", period))
        else:
            results.append(_entry("GSTR-1 IFF (optional)", "qrdp_iff",
                                  _advance(after_year, after_month, 13), period))
        results.append(_note_entry("GSTR-3B", "QRDP files GSTR-3B quarterly, not monthly", period))
        return results
    results.append(_entry("GSTR-1", "monthly", _advance(after_year, after_month, 11), period))
    results.append(_entry("GSTR-3B", "monthly", _advance(after_year, after_month, 20), period))
    return results


# Rule 61(1)(ii) / Notif 82/2020-CT: GSTR-3B for QRMP filers is due on the 22nd for principal
# places of business in these States/UTs, and on the 24th for every other State/UT (incl.
# Delhi, Punjab, Haryana, Rajasthan, UP, Bihar, WB, Odisha, J&K, Ladakh, Chandigarh,
# Himachal, Uttarakhand, Sikkim and the north-east).
# 22nd: Chhattisgarh 22, MP 23, Gujarat 24, DNH&DD 26 (+25 legacy Daman & Diu), Maharashtra 27,
# Karnataka 29, Goa 30, Lakshadweep 31, Kerala 32, Tamil Nadu 33, Puducherry 34, A&N 35,
# Telangana 36, Andhra Pradesh 37.
_QRMP_22ND = {"22", "23", "24", "25", "26", "27", "29", "30", "31", "32", "33", "34", "35",
              "36", "37"}


def _entry(form: str, filer: str, due: date, period: str) -> dict:
    rule = next((r for r in DEADLINE_RULES if r["form"] == form.split(" ")[0]), {})
    override = DEADLINE_OVERRIDES.get((form.split(" ")[0], period))
    return {"form": form, "period": period, "due_date": due.isoformat(),
            "rule": rule.get("desc", ""), "override": override}


def _note_entry(form: str, note: str, period: str) -> dict:
    return {"form": form, "period": period, "due_date": None, "rule": note, "override": None}


def advance_tax_schedule(annual_income: float, regime: str = "new") -> dict:
    """Quarterly advance-tax instalments for projected annual income."""
    from .itr_crossover import compute_tax
    tax = compute_tax(annual_income, regime)
    schedule = []
    for inst in ADVANCE_TAX_INSTALLMENTS:
        due = inst["label"]
        schedule.append({"instalment": due, "cumulative_share": inst["share"],
                         "cumulative_amount": round(tax["total_tax"] * inst["share"], 2)})
    return {"annual_income": annual_income, "regime": regime,
            "annual_tax": tax["total_tax"], "instalments": schedule}


_FILER_ALIASES = {"monthly": "monthly", "qrdp": "qrdp", "qrmp": "qrdp",
                  "quarterly": "qrdp", "composition": "composition", "cmp": "composition"}


def _normalise_filer_type(filer_type: str) -> str:
    """QRMP is the scheme's official name; "qrdp" is this package's original spelling.
    An unknown value is an error, never a silent fall back to monthly dates."""
    key = (filer_type or "").strip().lower()
    if key not in _FILER_ALIASES:
        raise ValueError(f"filer_type must be one of monthly, qrmp, composition; got {filer_type!r}")
    return _FILER_ALIASES[key]
