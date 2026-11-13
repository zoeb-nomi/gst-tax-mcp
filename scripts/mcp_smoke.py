import asyncio
import json
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[1]


async def main() -> None:
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "gst_mcp.server"], cwd=str(ROOT))
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            print(f"tools: {len(tools.tools)}")
            for t in tools.tools:
                print("-", t.name)
            prof = json.dumps(json.loads((ROOT / "fixtures" / "priya_pickles" / "profile.json").read_text()))
            res = await session.call_tool("gst_applicability", {"profile": prof})
            out = json.loads(res.content[0].text)
            print("applicability:", out["needs_registration"], out["composition_eligible"])
            inv = ROOT / "fixtures" / "priya_pickles" / "einvoice_meridian.json"
            res = await session.call_tool("validate_einvoice_tool",
                                          {"einvoice": str(inv), "supplier_ato": 6_20_00_000})
            out = json.loads(res.content[0].text)
            print("einvoice valid:", out["valid"])


if __name__ == "__main__":
    asyncio.run(main())
