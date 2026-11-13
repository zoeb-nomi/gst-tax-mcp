"""LangGraph GST filing agent.

Runs a ReAct agent whose tools are the nine tools exposed by the GST MCP
server (loaded over stdio via langchain-mcp-adapters). One complete session
walks a client quarter from applicability to the ITR crossover checks and
prints a filing pack.

Usage:
    .venv/bin/python -m gst_mcp.agent --fixtures fixtures/priya_pickles
    (needs OPENROUTER_API_KEY; model via GST_AGENT_MODEL, default z-ai/glm-5.3-flash)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SYSTEM_PROMPT = """You are a GST filing assistant for Indian small businesses.
You are preparing one quarterly filing session for the client whose data files
are given to you. Call the tools in a sensible order and use their outputs to
build the final filing pack. Never invent rates or rules; the tools are the
source of truth. Where a tool flags something (mismatch, blocked credit,
deadline), carry the flag into your summary in plain language.

Suggested order for a complete session:
1. gst_applicability on the profile
2. gst_filing_deadlines for the quarter (use the filer type from applicability)
3. calc_gst_liability on the freight invoice (reverse charge)
4. reconcile_itc_tool with the books and GSTR-2B files
5. gstr1_summary_tool on the outward invoices file
6. validate_einvoice_tool on the e-invoice file (pass supplier_ato from the profile)
7. itr_turnover_reconcile_tool and itr_advance_tax_estimate_tool with the ITR file
Finish with a section called FILING PACK with: liability due, ITC position,
GSTR-1 totals, deadlines, flags to fix before filing, and ITR crossover notes.
Keep numbers exactly as the tools returned them."""


def _build_user_message(fixtures: Path, period: str) -> str:
    def p(name: str) -> str:
        return str(fixtures / name)

    itr = json.loads((fixtures / "itr_fy2025_26.json").read_text())
    return f"""Prepare the GST filing session for this client.

Client profile: {p('profile.json')}
Outward invoices for the quarter: {p('outward_invoices_q2_2026.json')}
Purchase register (books ITC): {p('books_purchases_q2_2026.json')}
GSTR-2B as downloaded from the portal: {p('gstr2b_q2_2026.json')}
E-invoice awaiting validation: {p('einvoice_meridian.json')}
Freight invoice paid under reverse charge: taxable value Rs 8,000, SAC 996411,
supplier in Maharashtra, reverse charge applies.

ITR crossover figures (read these numbers from this message; the tools take
numbers, not files):
- GSTR-3B annual turnover FY 2025-26: Rs {itr['gstr3b_annual_turnover']:,}
- ITR gross receipts FY 2025-26: Rs {itr['itr_gross_receipts']:,}
- ITR presumptive scheme: {itr['itr_presumptive_scheme']}
- Projected income FY 2026-27: Rs {itr['projected_income_fy2026_27']:,}

Filing period: {period} (Indian fiscal quarter Q2 of FY 2026-27 = July-September 2026).
Use the recommended_filer_type from the applicability tool for the deadlines call."""


async def run(fixtures: Path, model: str, period: str = "2026-Q2",
              max_iterations: int = 30) -> str:
    from langchain_mcp_adapters.client import MultiServerMCPClient
    from langchain_openai import ChatOpenAI
    from langgraph.prebuilt import create_react_agent

    server_params = {
        "gst_tax_mcp": {
            "command": sys.executable,
            "args": ["-m", "gst_mcp.server"],
            "cwd": str(ROOT),
            "transport": "stdio",
        }
    }
    lines: list[str] = []

    client = MultiServerMCPClient(server_params)
    tools = await client.get_tools()
    llm = ChatOpenAI(model=model, base_url="https://openrouter.ai/api/v1",
                     api_key=os.environ["OPENROUTER_API_KEY"], temperature=0)
    agent = create_react_agent(llm, tools, prompt=SYSTEM_PROMPT)
    inputs = {"messages": [{"role": "user",
                            "content": _build_user_message(fixtures, period)}]}
    steps = 0
    async for update in agent.astream(inputs, stream_mode="updates"):
        for node, payload in update.items():
            messages = payload.get("messages", [])
            for msg in messages:
                kind = msg.__class__.__name__
                calls = getattr(msg, "tool_calls", None) or []
                for call in calls:
                    lines.append(f"[{node}] -> {call['name']}({json.dumps(call['args'])[:160]})")
                content = getattr(msg, "content", "")
                if content and kind != "AIMessage":
                    text = content if isinstance(content, str) else json.dumps(content)
                    lines.append(f"[{node}/{kind}] {text[:400]}")
                elif content and kind == "AIMessage" and not calls:
                    lines.append(f"[agent] {content}")
        steps += 1
        if steps > max_iterations:
            lines.append("[aborted] max iterations reached")
            break
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description="LangGraph GST filing agent")
    ap.add_argument("--fixtures", default=str(ROOT / "fixtures" / "priya_pickles"))
    ap.add_argument("--model", default=os.environ.get("GST_AGENT_MODEL", "z-ai/glm-5.3-flash"))
    ap.add_argument("--period", default="2026-Q2")
    args = ap.parse_args()
    transcript = asyncio.run(run(Path(args.fixtures), args.model, args.period))
    print(transcript)


if __name__ == "__main__":
    main()
