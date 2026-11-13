"""Reference data for the GST MCP server.

Curated sample tables: GST rate schedule (with the 56th Council / Sep-2025
restructure), state codes, filing deadline rules, blocked-ITC rules and
registration thresholds. Not a substitute for the CBIC notifications —
see README before production use.
"""
from __future__ import annotations

from datetime import date

STATE_CODES: dict[str, str] = {
    "01": "Jammu & Kashmir", "02": "Himachal Pradesh", "03": "Punjab",
    "04": "Chandigarh", "05": "Uttarakhand", "06": "Haryana", "07": "Delhi",
    "08": "Rajasthan", "09": "Uttar Pradesh", "10": "Bihar", "11": "Sikkim",
    "12": "Arunachal Pradesh", "13": "Nagaland", "14": "Manipur",
    "15": "Mizoram", "16": "Tripura", "17": "Meghalaya", "18": "Assam",
    "19": "West Bengal", "20": "Jharkhand", "21": "Odisha",
    "22": "Chattisgarh", "23": "Madhya Pradesh", "24": "Gujarat",
    "26": "Dadra & Nagar Haveli and Daman & Diu", "27": "Maharashtra",
    "29": "Karnataka", "30": "Goa", "31": "Lakshadweep", "32": "Kerala",
    "33": "Tamil Nadu", "34": "Puducherry", "35": "Andaman & Nicobar",
    "36": "Telangana", "37": "Andhra Pradesh", "38": "Ladakh",
    "97": "Other Territory",
}

# Registration thresholds by State (aggregate turnover, intra-State supplies).
# Goods: Rs 40L, except Rs 20L in the ten States excluded by Notification
# 10/2019-CT (7 Mar 2019, w.e.f. 1 Apr 2019): Arunachal Pradesh, Manipur,
# Meghalaya, Mizoram, Nagaland, Puducherry, Sikkim, Telangana, Tripura,
# Uttarakhand. Assam, Himachal Pradesh and J&K are NOT in that list (Rs 40L).
GOODS_THRESHOLD_20L_STATES = {"12", "14", "17", "15", "13", "34", "11", "36", "16", "05"}
# Services: Rs 20L, except Rs 10L in Manipur, Mizoram, Nagaland and Tripura
# (CBIC "GST - An Update", 1 Apr 2019; Notification 10/2017-IT services limit).
SERVICES_THRESHOLD_10L_STATES = {"14", "15", "13", "16"}
# Composition limit: Rs 1.5 cr, but Rs 75L in Arunachal Pradesh, Manipur,
# Meghalaya, Mizoram, Nagaland, Sikkim, Tripura, Uttarakhand
# (Notification 14/2019-CT, 7 Mar 2019). Telangana and Puducherry keep Rs 1.5 cr.
COMPOSITION_75L_STATES = {"12", "14", "17", "15", "13", "11", "16", "05"}

# GST rate schedule, keyed by HSN/SAC prefix, effective-date aware.
# Fields: prefix, description, rate (cgst+sgst or igst, as fraction expressed
# in %), cess %, effective_from. The 56th Council restructure (22 Sep 2025)
# collapsed 12% mostly into 5% and 28% into 18% / 40%.
RATE_TABLE: list[dict] = [
    # Rice: nil (Notif 2/2017-CT(Rate)) unless pre-packaged and labelled, then 5%
    # (Notif 1/2017-CT(Rate) Sch I; Notif 9/2025-CT(Rate) Sch I S.No.48 after 22 Sep 2025).
    # `condition` marks a row that depends on a fact the code alone cannot show.
    # classify() answers with the taxable (pre-packaged) row by default and lists
    # the unconditional alternatives under `alternatives`.
    {"prefix": "1006", "desc": "Rice (pre-packaged & labelled)", "rate": 5.0, "cess": 0.0,
     "effective_from": date(2017, 7, 1), "condition": "prepackaged"},
    {"prefix": "1006", "desc": "Rice (loose / non-pre-packaged, nil rated)", "rate": 0.0, "cess": 0.0,
     "effective_from": date(2017, 7, 1), "condition": "loose"},
    {"prefix": "3401", "desc": "Soaps", "rate": 18.0, "cess": 0.0,
     "effective_from": date(2017, 7, 1)},
    {"prefix": "3401", "desc": "Soaps", "rate": 5.0, "cess": 0.0,
     "effective_from": date(2025, 9, 22)},
    {"prefix": "2005", "desc": "Pickles and other preserved vegetables", "rate": 12.0, "cess": 0.0,
     "effective_from": date(2017, 7, 1)},
    {"prefix": "2005", "desc": "Pickles and other preserved vegetables", "rate": 5.0, "cess": 0.0,
     "effective_from": date(2025, 9, 22)},
    {"prefix": "1905", "desc": "Bakery products, biscuits", "rate": 18.0, "cess": 0.0,
     "effective_from": date(2017, 7, 1)},
    {"prefix": "1905", "desc": "Bakery products, biscuits", "rate": 5.0, "cess": 0.0,
     "effective_from": date(2025, 9, 22)},
    {"prefix": "3305", "desc": "Shampoos, hair care", "rate": 18.0, "cess": 0.0,
     "effective_from": date(2017, 7, 1)},
    {"prefix": "3305", "desc": "Shampoos, hair care", "rate": 5.0, "cess": 0.0,
     "effective_from": date(2025, 9, 22)},
    {"prefix": "3304", "desc": "Beauty / make-up preparations", "rate": 18.0, "cess": 0.0,
     "effective_from": date(2017, 7, 1)},
    # Small cars: petrol <=1200cc / diesel <=1500cc and length <=4m (Notif 1/2017-CT(Rate)
    # Sch IV, 28% + 1% cess / 3% for diesel). From 22 Sep 2025: 18% (Notif 9/2025-CT(Rate)
    # Sch II), compensation cess nil. Only the sub-headings that can hold small cars are
    # listed here; the length/engine test still has to be met (`condition`).
    {"prefix": "870321", "desc": "Motor cars, petrol <=1000cc (small car if length <=4m)",
     "rate": 28.0, "cess": 1.0, "effective_from": date(2017, 7, 1), "condition": "small_car"},
    {"prefix": "870321", "desc": "Motor cars, petrol <=1000cc (small car if length <=4m)",
     "rate": 18.0, "cess": 0.0, "effective_from": date(2025, 9, 22), "condition": "small_car"},
    {"prefix": "870322", "desc": "Motor cars, petrol 1000-1500cc (small car only if <=1200cc and length <=4m)",
     "rate": 28.0, "cess": 1.0, "effective_from": date(2017, 7, 1), "condition": "small_car"},
    {"prefix": "870322", "desc": "Motor cars, petrol 1000-1500cc (small car only if <=1200cc and length <=4m)",
     "rate": 18.0, "cess": 0.0, "effective_from": date(2025, 9, 22), "condition": "small_car"},
    {"prefix": "870331", "desc": "Motor cars, diesel <=1500cc (small car if length <=4m)",
     "rate": 28.0, "cess": 3.0, "effective_from": date(2017, 7, 1), "condition": "small_car"},
    {"prefix": "870331", "desc": "Motor cars, diesel <=1500cc (small car if length <=4m)",
     "rate": 18.0, "cess": 0.0, "effective_from": date(2025, 9, 22), "condition": "small_car"},
    # Every other 8703 car (mid/large cars, SUVs, 870323+): 28% + cess before, 40% with no
    # compensation cess from 22 Sep 2025 (Notif 9/2025-CT(Rate) Sch III S.No.5; cess nil
    # per the 22 Sep 2025 Compensation Cess (Rate) notification; PIB 3 Sep 2025).
    {"prefix": "8703", "desc": "Motor cars (other / large / SUV)", "rate": 28.0, "cess": 15.0,
     "effective_from": date(2017, 7, 1)},
    {"prefix": "8703", "desc": "Motor cars (other / large / SUV)", "rate": 40.0, "cess": 0.0,
     "effective_from": date(2025, 9, 22)},
    # Motorcycles <=350cc: 28% with NO cess before 22 Sep 2025 (Compensation Cess Notif
    # 1/2017 S.No.53 applies 3% only above 350cc), 18% from 22 Sep 2025. Above 350cc:
    # 28% + 3% cess, then 40% (Notif 9/2025-CT(Rate) Sch III).
    {"prefix": "8711", "desc": "Motorcycles (<=350cc)", "rate": 28.0, "cess": 0.0,
     "effective_from": date(2017, 7, 1)},
    {"prefix": "8711", "desc": "Motorcycles (<=350cc)", "rate": 18.0, "cess": 0.0,
     "effective_from": date(2025, 9, 22)},
    {"prefix": "871140", "desc": "Motorcycles (>350cc)", "rate": 28.0, "cess": 3.0,
     "effective_from": date(2017, 7, 1)},
    {"prefix": "871140", "desc": "Motorcycles (>350cc)", "rate": 40.0, "cess": 0.0,
     "effective_from": date(2025, 9, 22)},
    {"prefix": "871150", "desc": "Motorcycles (>350cc)", "rate": 28.0, "cess": 3.0,
     "effective_from": date(2017, 7, 1)},
    {"prefix": "871150", "desc": "Motorcycles (>350cc)", "rate": 40.0, "cess": 0.0,
     "effective_from": date(2025, 9, 22)},
    {"prefix": "2523", "desc": "Cement", "rate": 28.0, "cess": 0.0,
     "effective_from": date(2017, 7, 1)},
    {"prefix": "2523", "desc": "Cement", "rate": 18.0, "cess": 0.0,
     "effective_from": date(2025, 9, 22)},
    {"prefix": "2402", "desc": "Cigarettes, tobacco", "rate": 28.0, "cess": 12.0,
     "effective_from": date(2017, 7, 1)},
    # From 1 Feb 2026 tobacco is 40% GST with compensation cess nil (excise/health cess
    # replace it): Notif 19/2025-CT(Rate); Compensation Cess (Rate) Notif 03/2025.
    {"prefix": "2402", "desc": "Cigarettes, tobacco (40% GST, cess nil; excise duty is separate)",
     "rate": 40.0, "cess": 0.0, "effective_from": date(2026, 2, 1)},
    {"prefix": "8544", "desc": "Insulated wire and cables", "rate": 18.0, "cess": 0.0,
     "effective_from": date(2017, 7, 1)},
    {"prefix": "8471", "desc": "Laptops, computers", "rate": 18.0, "cess": 0.0,
     "effective_from": date(2017, 7, 1)},
    {"prefix": "8708", "desc": "Motor vehicle parts", "rate": 28.0, "cess": 0.0,
     "effective_from": date(2017, 7, 1)},
    {"prefix": "8708", "desc": "Motor vehicle parts", "rate": 18.0, "cess": 0.0,
     "effective_from": date(2025, 9, 22)},
    {"prefix": "998311", "desc": "IT consulting and software services", "rate": 18.0, "cess": 0.0,
     "effective_from": date(2017, 7, 1)},
    # 997212 is renting of non-residential property, not legal services (SAC 9972).
    {"prefix": "997212", "desc": "Renting of commercial / non-residential property", "rate": 18.0, "cess": 0.0,
     "effective_from": date(2017, 7, 1)},
    # SAC 9982 = legal and accounting services (998211-998219). Advocate services to a
    # business entity are on reverse charge: Notif 13/2017-CT(Rate) Sl.2.
    {"prefix": "9982", "desc": "Legal and accounting services (advocate to business: RCM, Notif 13/2017 Sl.2)",
     "rate": 18.0, "cess": 0.0, "effective_from": date(2017, 7, 1)},
    # GTA road goods transport is SAC 996511 (9964 is passenger transport). 5% without ITC
    # (RCM to registered recipients), Notif 11/2017-CT(Rate) as amended; RCM Notif 13/2017 Sl.1.
    # The 12% (now 18%) with-ITC option is not modelled.
    {"prefix": "996511", "desc": "Goods transport by road (GTA, 5% no ITC; RCM per Notif 13/2017 Sl.1)",
     "rate": 5.0, "cess": 0.0, "effective_from": date(2017, 7, 1)},
    {"prefix": "999799", "desc": "Personal care services (salons, gyms, yoga)", "rate": 18.0, "cess": 0.0,
     "effective_from": date(2017, 7, 1)},
    {"prefix": "999799", "desc": "Personal care services (salons, gyms, yoga)", "rate": 5.0, "cess": 0.0,
     "effective_from": date(2025, 9, 22)},
    {"prefix": "997331", "desc": "Life and health insurance", "rate": 18.0, "cess": 0.0,
     "effective_from": date(2017, 7, 1)},
    {"prefix": "997331", "desc": "Life and health insurance (individual policies exempt)", "rate": 0.0, "cess": 0.0,
     "effective_from": date(2025, 9, 22)},
]

# Registration threshold (aggregate turnover), in rupees.
THRESHOLDS = {
    "goods_normal": 40_00_000,
    "goods_special": 20_00_000,
    "services_normal": 20_00_000,
    "services_special": 10_00_000,
    "composition_limit": 1_50_00_000,
    "composition_limit_special": 75_00_000,
    "composition_services_only": 50_00_000,
    "einvoice_ato": 5_00_00_000,
    "qrdp_ato": 5_00_00_000,
}

COMPOSITION_RATES = {
    "trader_manufacturer": 1.0,
    "restaurant": 5.0,
    "service_provider_upto_50l": 6.0,
}

# Citations for the composition rule rows returned by check_applicability().
CITE_S10_1 = ("CGST Act s.10(1)-(2); limit Notif 14/2019-CT (Rs 1.5 cr, Rs 75L in eight States); "
              "rates CGST Rules r.7")
CITE_S10_2A = ("CGST Act s.10(2A); Notif 2/2019-CT(Rate), 7 Mar 2019, w.e.f. 1 Apr 2019 "
               "(3% central tax; same rate under the State notification)")
CITE_ECO_2023 = "CGST Act s.10(2)(d) and s.10(2A)(c) as amended by Finance Act 2023, w.e.f. 1 Oct 2023"

# s.10(1) second proviso: a s.10(1) taxpayer may also supply services (other than
# restaurant service, Sch II para 6(b)) up to 10% of turnover in the State in the
# preceding FY or Rs 5 lakh, whichever is higher. Above that, s.10(1) is closed
# and the s.10(2A) services scheme is the only composition route.
S10_1_SERVICES_ALLOWANCE = {"share": 0.10, "floor": 5_00_000}

# s.10(2A) / Notif 2/2019-CT(Rate): limit Rs 50L in the preceding FY in every State
# (no reduced-limit States), 3% CGST + 3% SGST/UTGST = 6%.
S10_2A = {"limit": 50_00_000, "cgst": 3.0, "sgst": 3.0}

# Notif 2/2019-CT(Rate), condition 1(vii) and Annexure: a person supplying these
# goods cannot use the 3% rate. Matched as HSN prefixes.
S10_2A_EXCLUDED_GOODS = [
    {"prefix": "2105", "desc": "Ice cream and other edible ice (2105 00 00)"},
    {"prefix": "21069020", "desc": "Pan masala (2106 90 20)"},
    {"prefix": "24", "desc": "Tobacco and manufactured tobacco substitutes (Chapter 24)"},
]

# Blocked credits, section 17(5) — subset keyed by HSN prefix / category.
BLOCKED_ITC: list[dict] = [
    # s.17(5)(a) blocks motor vehicles for transport of persons (seating <=13) only;
    # goods vehicles (8704) are outside the block.
    {"match": "8703", "reason": "Motor vehicles for transport of persons (17(5)(a)) unless eligible business use"},
    {"match": "1905", "reason": "Food and beverages (17(5)(b)) unless used for further supply"},
    {"match": "9963", "reason": "Food and beverages (17(5)(b)) unless used for further supply"},
    {"match": "9303", "reason": "Club / health / fitness membership (17(5)(b))"},
]

# Filing deadline rules. day_of: 11 = 11th of following month, etc.
DEADLINE_RULES = [
    {"form": "GSTR-1", "filer": "monthly", "day": 11,
     "desc": "Outward supplies statement, monthly filer"},
    {"form": "GSTR-1", "filer": "qrdp_quarter", "day": 13,
     "desc": "Outward supplies statement, quarterly filer (QRDP), month after quarter"},
    {"form": "GSTR-1", "filer": "qrdp_iff", "day": 13,
     "desc": "Invoice Furnishing Facility, QRMP months 1 and 2 only (Rule 59(2))"},
    {"form": "GSTR-3B", "filer": "monthly", "day": 20,
     "desc": "Summary return, monthly filer"},
    {"form": "GSTR-3B", "filer": "qrdp_quarter_catX", "day": 22,
     "desc": "Summary return, QRDP category X states"},
    {"form": "GSTR-3B", "filer": "qrdp_quarter_catXp", "day": 24,
     "desc": "Summary return, QRDP category X' states"},
    {"form": "PMT-06", "filer": "qrdp_quarter", "day": 25,
     "desc": "Challan-cum-statement (tax payment), QRDP"},
    {"form": "CMP-08", "filer": "composition", "day": 18,
     "desc": "Composition quarterly statement-cum-challan"},
    {"form": "GSTR-9", "filer": "annual", "day": 31, "month": 12,
     "desc": "Annual return (ATO > 2cr mandatory)"},
    {"form": "GSTR-4", "filer": "composition_annual", "day": 30, "month": 6,
     "desc": "Composition annual return"},
    {"form": "ITR-3/4", "filer": "itr_non_audit", "day": 31, "month": 7,
     "desc": "Income tax return, non-audit cases"},
    {"form": "ITR-3/5/6", "filer": "itr_audit", "day": 31, "month": 10,
     "desc": "Income tax return, audit cases"},
]

ADVANCE_TAX_INSTALLMENTS = [
    {"date": (6, 15), "share": 0.15, "label": "by 15 June"},
    {"date": (9, 15), "share": 0.45, "label": "by 15 September"},
    {"date": (12, 15), "share": 0.75, "label": "by 15 December"},
    {"date": (3, 15), "share": 1.00, "label": "by 15 March"},
]

# Historical deadline overrides (mechanism demo; current FY has none).
DEADLINE_OVERRIDES: dict[tuple[str, str], str] = {
    ("GSTR-1", "2024-04"): "Extended due to GSTN portal glitch (historical example)",
}

EINVOICE_MANDATE = {"ato_threshold": 5_00_00_000, "effective_from": date(2023, 8, 1)}
