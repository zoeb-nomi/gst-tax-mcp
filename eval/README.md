# GST MCP eval

A small, sourced check of two things:

1. **Tool accuracy** - does each GST MCP tool return the legally correct answer?
2. **No-tools baseline** (later) - how well does a model answer the same questions without the tools?

47 cases (40 from the first build, 7 services-composition cases added 13 Nov 2026), one checkable field each. Expected answers were derived from the law and
confirmed against a source that was opened during authoring (see `source` on each
case). They were **not** copied from the tool's output; where the tool and the law
disagree, the tool loses and the case is a finding (below).

## Files

| File | Purpose |
|---|---|
| `cases.jsonl` | The 47 cases: `id, category, question, tool, tool_args, expected, answer_type, source, confidence` |
| `questions.jsonl` | `id` + `question` only, for the blind baseline |
| `run_tools.py` | Runs each case through the matching tool, compares, writes `results_tools.json` |
| `score_baseline.py` | Scores `baseline_answers.jsonl` against `expected`, writes `results_baseline.json`; `--dry-run` self-tests the parsers |
| `results_tools.json` | Latest tool run (per-case expected vs tool output) |

## Run

```bash
pip install -r requirements.txt            # repo root
python eval/run_tools.py                   # no network, no keys
python eval/score_baseline.py --dry-run    # tests the answer parser on a fake file
python eval/score_baseline.py              # needs eval/baseline_answers.jsonl
```

Baseline protocol: give the model only `questions.jsonl` (no tools, no web), ask it to
reason briefly and finish with a line `Answer: <value>` (yes/no, a percentage, rupees, an
ISO date, or a number). Write `{"id", "answer_text"}` per line to `eval/baseline_answers.jsonl`.
Without an `Answer:` line the scorer falls back to the last number/date or first yes/no in
the text, which is less reliable. Unanswered = wrong.

## Categories (47 cases)

| Category | Cases |
|---|---|
| registration_composition (thresholds, special-category states, composition) | 8 |
| services_composition (s.10(2A): Rs 50L limit, 6% rate, the Notif 2/2019-CT(Rate) exclusions, s.10(1) vs s.10(2A)) | 7 |
| rate_lookup (incl. 22 Sep 2025 GST 2.0 changes, 40% slab, cess) | 7 |
| filing_deadlines (monthly, QRMP, state groups, IFF) | 7 |
| itr_presumptive_tax (44AD/44ADA, new-regime tax, marginal relief) | 5 |
| tax_split_liability (CGST/SGST vs IGST, discount, cess) | 4 |
| einvoice_hsn | 3 |
| itc_blocked (s.17(5)) | 3 |
| reverse_charge (GTA, advocate) | 2 |
| gstr1_tables | 1 |

## Sourcing

Services composition (`SCOMP-*`): Notification 2/2019-Central Tax (Rate), read from the GST Council PDF (conditions 1(i)-(vii), the Annexure, para 2 on interest); CGST Act s.10 from the cggst.com text, including the footnotes on the Finance Act 2023 change that limits the e-commerce bar to services from 1 Oct 2023. All `confidence: high`.


Sources opened via WebFetch: CBIC rule pages (r.59, r.61, r.62), GST Council copies of
Notifications 10/2019, 14/2019, 82/2020 and 13/2017 (Rate), CBIC "GST - An Update" (1 Apr 2019),
PIB releases (Sept 2025 rate rationalisation; HSN digits), CBIC GST ready reckoner for
Notification 9/2025-CT(Rate) (mirror copy), CGST Act sections 10, 15, 17 (cggst.com texts),
the Income Tax Dept's ITR-4 help page, and secondary firm/news pages where no primary text was
fetchable (ClearTax, LiveLaw, Taxscan, Lakshmikumaran, Business Standard, allindiaitr).
Cases that lean on secondary sources are marked `confidence: medium`
(REG-04, REG-05, REG-06, RATE-05, RATE-07, G1-01). Caveats:

- Several fetches were summarised by a model; rates in `RATE-*` come from the ready-reckoner
  mirror of Notification 9/2025, not the Gazette PDF. Re-verify against CBIC before relying on them.
- Due dates assume no ad-hoc extension notification; all chosen dates fall on working days.
- `presumptive_check` (ITR-01..03) is in `gst_mcp/core` but is **not exposed** by `server.py`;
  the eval calls the core function.
- Income-tax cases use the Income-tax Act, 1961 for FY 2025-26.

## Results

| Run | Score | Notes |
|---|---|---|
| Tools (current code, 40 cases) | **22 / 40 (55.0%)** | 18 disagreements with the law, listed below |
| No-tools baseline | pending | run after `baseline_answers.jsonl` exists |

Tool score by category: einvoice_hsn 3/3, itr_presumptive_tax 4/5, tax_split_liability 3/4,
itc_blocked 2/3, rate_lookup 4/7, filing_deadlines 3/7, registration_composition 3/8,
gstr1_tables 0/1, reverse_charge 0/2.

## Findings (tool vs law)

The tool was not edited and no expected value was changed to match it.

| Case | Tool says | Law says | Source |
|---|---|---|---|
| REG-02 Telangana goods Rs 30L | no registration (40L) | register (20L goods limit in Telangana) | Notif 10/2019-CT; CBIC "GST - An Update" |
| REG-03 Manipur goods Rs 15L | register (10L) | not required (20L goods) | same |
| REG-04 Assam goods Rs 30L | register (20L) | not required (40L; Assam not in the 10 States) | same |
| REG-05 Uttarakhand services Rs 15L | register (10L) | not required (services 10L only in Manipur, Mizoram, Nagaland, Tripura) | CBIC "GST - An Update" |
| REG-08 Sikkim composition Rs 90L | eligible (1.5cr) | not eligible (75L in Sikkim, Uttarakhand + 6) | Notif 14/2019-CT |
| RATE-04 prepacked rice 1006 | 0% | 5% (table cannot tell branded from unbranded) | Notif 9/2025, Sch I S.No.48 |
| RATE-06 2,500cc SUV 8703 | 18% | 40% (prefix table maps all 8703 to the small-car row) | Notif 9/2025, Sch III |
| RATE-07 cigarettes 2402, 1 Mar 2026 | 28% + 12% cess | 40%, cess nil from 1 Feb 2026 | Notif 19/2025-CT(Rate); Comp. Cess (Rate) 03/2025 |
| LIAB-04 motorcycle <=350cc, Jun 2025 | Rs 34,000 (6% cess) | Rs 28,000 (no cess at or below 350cc) | Comp. Cess Notif 1/2017 S.No.53 |
| RCM-01 advocate, SAC 998212 | not covered (tool lists legal as 997212) | Rs 18,000 | Notif 13/2017 (Rate) Sl.2; SAC 9982 |
| RCM-02 GTA, SAC 996511 | not covered (tool lists GTA as 996411) | Rs 2,500 | Notif 13/2017 (Rate) Sl.1 |
| ITC-02 goods truck 8704 | blocked | allowed (s.17(5)(a) covers passenger vehicles only) | CGST Act s.17(5)(a) |
| DL-04 Delhi QRMP GSTR-3B | 22 Jul | 24 Jul | CGST Rules r.61(1)(ii) |
| DL-05 Kerala QRMP GSTR-3B | 24 Jul | 22 Jul | r.61(1)(ii) |
| DL-06 IFF for month 1 | none | 13th of next month | r.59(2) |
| DL-07 IFF for month 3 | offered | not available | r.59(2) |
| G1-01 B2C inter-State Rs 1.5L | Table 7 (threshold 2.5L) | Table 5 (threshold 1L) | Notif 12/2024-CT |
| ITR-05 salaried Rs 12.8L gross | Rs 63,180 | Rs 5,200 (87A marginal relief) | s.87A; allindiaitr worked example |

Other checks the same code gets wrong but the eval does not include (found while reading the code):
`BLOCKED_ITC` also blocks any 1905 bakery item and any 8703 purchase for resale (the exceptions
in s.17(5) are not modelled); the QRMP state group set (`_CAT_XP`) puts Kerala, Tamil Nadu,
Telangana, Andhra Pradesh, Puducherry and Andaman in the 24th group and leaves Delhi, Himachal,
Uttarakhand, Sikkim, J&K and Ladakh in the 22nd; an advance-tax schedule is returned in four
instalments even for 44AD/44ADA payers, who pay once by 15 March (s.211).

## Results

| Run | Score | What it means |
|---|---|---|
| Tools, first run (12 Nov 2026) | 22/40 | 18 legal errors in the rule tables: state thresholds, QRMP due-date groups, the 22 Sep 2025 rate changes, reverse-charge codes, IFF months, the B2C-large limit, s.87A marginal relief |
| Claude Haiku, no tools, blind | 33/40 | Answered from its own knowledge with only the questions in front of it. Misses: Telangana threshold, Uttarakhand services threshold, cigarettes after 1 Feb 2026, all three QRMP date-group cases, the B2C-large limit |
| Tools, after fixes | 40/40 | The rules were fixed against these same 40 cases, so this shows the 18 errors are gone. It is a regression check, not an accuracy estimate. A fresh held-out set is the next step |
| Tools, 13 Nov 2026, with `SCOMP-01..07` | 47/47 | The 7 new cases were written from the text of Notif 2/2019-CT(Rate) (GST Council copy) and CGST Act s.10(1)-(2A) (cggst.com text) before the code changed. The previous code scored 42/47: it had no s.10(2A) route, so a Rs 30 lakh service provider was shown the Rs 1.5 crore goods limit, and it let a service provider selling through a TCS-collecting app, or a pan masala seller, into composition. The no-tools baseline has not been run on these 7. |

Known gaps outside these 40 cases: section 17(5) treats bakery items (1905) as blocked in every case; one SAC label (9303) is wrong; small-car length and engine-size conditions are flagged, not enforced; advance tax for 44AD/44ADA filers is shown as four instalments instead of one by 15 March. Rates and thresholds come from CBIC notifications cited in the code; check them before filing. Not tax advice.
