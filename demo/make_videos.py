"""Build and render the public demo video (~3 min) from the MCP transcript.

    .venv/bin/python demo/make_videos.py

Reads demo/transcripts/filing_session.txt, splits the
transcript at the "== " section markers, adds title/closing cards and burned-in
subtitles, and renders a WebM video into demo/videos/.
"""
from __future__ import annotations

import json
from pathlib import Path

from render_video import render

HERE = Path(__file__).resolve().parent
OUT = HERE / "videos"

TOOLS_SCREEN = """== the nine tools ==
gst_applicability · classify_hsn_sac · calc_gst_liability
reconcile_itc_tool · gst_filing_deadlines · gstr1_summary_tool
validate_einvoice_tool
ITR crossover: itr_turnover_reconcile_tool · itr_advance_tax_estimate_tool
# deterministic logic: rates, thresholds, checksums, deadlines. no model in the loop"""


def load_sections(name: str) -> list[list[str]]:
    text = (HERE / "transcripts" / name).read_text().splitlines()
    sections: list[list[str]] = []
    cur: list[str] = []
    for line in text:
        if line.startswith("== ") and cur:
            sections.append(cur)
            cur = [line]
        else:
            cur.append(line)
    if cur:
        sections.append(cur)
    return sections


def term_sections(sections: list[list[str]], subs: dict[str, str],
                  title: str, hold: float = 7.5, final_hold: float = 9.0) -> list[dict]:
    segs = []
    for section in sections:
        head = next((l for l in section if l.startswith("== ")), "")
        key = next((k for k in subs if k in head), head)
        seg = {"type": "term", "title": title,
               "lines": [l for l in section if not l.startswith("# connected")
                         and not l.startswith("# gst_applicability")],
               "hold": hold, "final_hold": final_hold,
               "sub": subs.get(key, "")}
        segs.append(seg)
    return segs


def public_video() -> list[dict]:
    subs = {
        "== Step 0": "Priya sells pickles from Pune. Prior-year turnover Rs 42 lakh - "
                     "a small business that must file GST.",
        "== Step 1": "Verdict: registration is required (inter-state goods supply), and the "
                     "composition scheme is not available to her. Filer type: quarterly.",
        "== Step 2": "Quarterly (QRDP) dates for Maharashtra: GSTR-1 by 13 Oct, "
                     "GSTR-3B by 22 Oct, payment by 25 Oct.",
        "== Step 3": "Reverse-charge freight: Rs 400 self-assessed, paid in cash, "
                     "claimed back as ITC in the same return.",
        "== Step 4": "ITC reconciliation against GSTR-2B: claim Rs 1,620 now; the module "
                     "flags a blocked credit, a mismatch and an invoice missing from 2B.",
        "== Step 5": "GSTR-1 totals: Rs 6,99,600 taxable and Rs 25,980 tax, net of the "
                     "credit note. The Rs 3.2 lakh B2C order lands in the right table (5A).",
        "== Step 6": "E-invoicing is not mandatory below Rs 5 crore turnover, but the "
                     "buyer asked for an e-invoice-ready bill: it validates.",
        "== Step 7": "ITR crossover: ITR shows 5.5% more than GST turnover - above the 5% "
                     "band the department's comparators use. Explain it before a notice does.",
        "== Step 8": "Advance tax for next year: Rs 1,20,900 in four instalments, "
                     "new regime vs old compared automatically.",
        "== Filing pack": "The filing pack: what to file, what to pay, what to fix - "
                          "every number on this screen came from the tools.",
    }
    sections = load_sections("filing_session.txt")
    segs = [
        {"type": "title", "hold": 9,
         "lines": ["Filing GST with an agent", "Priya's Homemade Pickles · Q2 2026"],
         "sub": "One complete GST filing session, driven by the nine tools of the "
                "gst-tax-mcp server"},
        {"type": "title", "hold": 8,
         "lines": ["The quarter", "9 documents · Rs 6.99 lakh taxable · 1 credit note · 1 export"],
         "sub": "All client data is synthetic demo data; every number that follows is "
                "computed by the tools"},
        {"type": "term", "hold": 10, "title": "gst-tax-mcp",
         "lines": TOOLS_SCREEN.splitlines(),
         "sub": "The same server serves the agent and any other MCP client"},
    ]
    segs += term_sections(sections, subs, "Priya · Q2 2026 filing session")
    segs += [
        {"type": "title", "hold": 7,
         "lines": ["And the agent?"],
         "sub": "The same nine tools drive a LangGraph agent: see agent.py and the live "
                "session transcript in this repo"},
        {"type": "title", "hold": 14,
         "lines": ["What just happened", "registration → deadlines → reverse charge → ITC",
                   "→ GSTR-1 → e-invoice → ITR crossover → filing pack"],
         "sub": "9 tools · one MCP server · one LangGraph agent · zero spreadsheets"},
    ]
    return segs


def main() -> None:
    fps = 10
    jobs = [("public_demo", public_video())]
    for name, segs in jobs:
        json.dump(segs, (HERE / f"{name}.segments.json").open("w"), indent=1)
        est = sum((s.get("hold", 8) if s["type"] == "title"
                   else s.get("hold", 6) * max(1, _pages(s))) for s in segs)
        out = render(segs, OUT / f"{name}.webm", fps=fps)
        print(f"{name}: est {est:.0f}s, {out.name} {out.stat().st_size / 1e6:.1f} MB")


def _pages(seg: dict) -> int:
    import render_video as rv
    lines = []
    for raw in seg["lines"]:
        lines.extend(rv.wrap(raw, 88))
    return max(1, -(-len(lines) // 20))


if __name__ == "__main__":
    main()
