"""
Mock financial MCP server — stands in for your real ERP / trade-execution
MCP servers so the whole pattern can be demonstrated end to end without
touching a production system.

Exposes two tools that match the talk's reference scenario:
  - erp.query      (read,  low risk)  -> returns GL balances
  - trade.correct  (write, high risk) -> books a correction

Serves MCP over Streamable HTTP so the Gateway can reach it across the
cluster. Run locally: python server.py
"""

import os

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("financial-mcp", host="0.0.0.0", port=int(os.environ.get("PORT", "9000")))

# Deliberately includes a variance so the demo has something to escalate.
_LEDGER = {
    "TRD-2026-04471": {"book_value": 1_250_000_000, "confirmed_value": 1_200_000_000},
}


@mcp.tool(name="erp.query")
def erp_query(business_key: str) -> dict:
    """Read GL balances for a trade. Read-only, low risk."""
    row = _LEDGER.get(business_key)
    if not row:
        return {"business_key": business_key, "found": False}
    variance = row["book_value"] - row["confirmed_value"]
    return {
        "business_key": business_key,
        "found": True,
        "book_value": row["book_value"],
        "confirmed_value": row["confirmed_value"],
        "variance": variance,
    }


@mcp.tool(name="trade.correct")
def trade_correct(business_key: str, amount: int) -> dict:
    """Book a correction against a trade. Write, high risk — gated by policy."""
    row = _LEDGER.get(business_key)
    if not row:
        return {"business_key": business_key, "corrected": False, "error": "unknown trade"}
    row["book_value"] -= amount
    return {
        "business_key": business_key,
        "corrected": True,
        "amount": amount,
        "new_book_value": row["book_value"],
    }


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
