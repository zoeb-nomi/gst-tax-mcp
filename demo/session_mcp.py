"""Shared MCP client plumbing for the demo session drivers."""
from __future__ import annotations

import asyncio
import contextlib
import io
import json
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[1]


class Session:
    """Drives one MCP server over stdio and records a plain transcript."""

    def __init__(self, title: str) -> None:
        self.lines: list[str] = []
        self.title = title

    def say(self, text: str = "") -> None:
        self.lines.append(text)

    async def call(self, session: ClientSession, tool: str, args: dict,
                   keep: list[str] | None = None) -> dict:
        shown_args = {k: (v.replace(str(ROOT) + "/", "~/") if isinstance(v, str) else v)
                      for k, v in args.items()}
        self.say(f"$ {tool} {json.dumps(shown_args, ensure_ascii=False)}")
        res = await session.call_tool(tool, args)
        out = json.loads(res.content[0].text)
        shown = out if keep is None else {k: out[k] for k in keep if k in out}
        self.say(json.dumps(shown, indent=2, ensure_ascii=False))
        return out

    async def _run(self, steps) -> None:
        params = StdioServerParameters(command=sys.executable,
                                       args=["-m", "gst_mcp.server"], cwd=str(ROOT))
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                self.say(f"# connected to gst-tax-mcp over stdio, {len(tools.tools)} tools:")
                self.say("# " + ", ".join(t.name for t in tools.tools))
                self.say()
                await steps(self, session)

    def run(self, steps) -> list[str]:
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            asyncio.run(self._run(steps))
        return self.lines

    def save(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(self.lines) + "\n")
        return path


def money(x) -> str:
    return f"Rs {x:,.2f}"
