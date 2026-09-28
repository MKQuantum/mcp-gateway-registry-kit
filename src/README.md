# src/ — the working implementation

Five pieces, each independently replaceable.

| Path | What it is | Language |
|---|---|---|
| `policy/` | The four guardrails as one Rego module + its test suite | Rego (OPA) |
| `gateway/` | Policy Enforcement Point — verifies identity, calls OPA, proxies allowed calls | Python / FastAPI |
| `worker/` | FluxNova External Task Worker — bridges BPMN service tasks to the Gateway | Python |
| `mock-mcp-server/` | Stand-in financial MCP server (`erp.query`, `trade.correct`) | Python / MCP SDK |
| `bpmn/` | The trade-reconciliation process model, with the step-up → Tasklist loop | BPMN 2.0 XML |

Run `cd policy && opa test . -v` with zero other setup — that's the fastest
way to confirm your environment is sane before standing up the full stack.

To run everything together, see [`../example/`](../example/README.md).
To build these five pieces yourself instead of reading them, see
[`../workshop/`](../workshop/BUILD-IT-YOURSELF.md).
