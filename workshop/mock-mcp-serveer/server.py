"""
PART 2 — Mock financial MCP server.

YOUR TASK: expose two MCP tools using the official Python SDK.

  erp.query(business_key)          -> dict with book_value, confirmed_value, variance
  trade.correct(business_key, amount) -> dict confirming the correction

Requirements:
  - server name "financial-mcp", host 0.0.0.0, port from env PORT (default 9000)
  - must serve over Streamable HTTP so the Gateway can reach it over the network
  - seed your ledger with TRD-2026-04471 where book_value != confirmed_value,
    so the demo has a real variance to escalate

CHECKPOINT: `python server.py` should start and log a URL on port 9000.

Docs: https://github.com/modelcontextprotocol/python-sdk
HINT: `from mcp.server.fastmcp import FastMCP`, decorate functions with
      @mcp.tool(name="..."), and finish with mcp.run(transport="streamable-http")
"""

import os

# TODO: import FastMCP and create the server instance

# TODO: seed ledger data

# TODO: @mcp.tool(name="erp.query") — read GL balances, return the variance

# TODO: @mcp.tool(name="trade.correct") — apply a correction, return new balance

if __name__ == "__main__":
    # TODO: mcp.run(transport="streamable-http")
    pass
