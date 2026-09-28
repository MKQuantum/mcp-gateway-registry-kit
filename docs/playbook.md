# The Gateway Playbook, mapped to this kit

The talk frames adoption as eight phases: Discovery → Classification →
Policy Design → Implementation → Testing → Deployment → Operations →
Retirement. This page maps each phase to what's actually in the kit —
and says plainly where the kit doesn't cover a phase yet, rather than
stretching something to fit.

| Phase | Talk's framing | What's in this kit | Coverage |
|---|---|---|---|
| **1. Discovery** | Inventory agents, servers, tools, data sources — "you can't govern what you haven't catalogued" | `src/policy/gateway_registry_data.json` → `rbac.role_scopes` *is* the catalog: which roles may call which tools | Partial — covers the policy-facing inventory, not a discovery scanner |
| **2. Classification** | Autonomy level, blast radius, data sensitivity → a risk tier | `input.action.risk_tier` ("low"/"high") in every policy input — consumed directly by `high_risk_action` / `step_up_required` | Covered — see `docs/policy-guide.md` |
| **3. Policy Design** | Turn risk into enforceable rules | `src/policy/gateway_registry_policy.rego` — this phase *is* this file | Covered |
| **4. Implementation** | Build gateway, integrate registry, connect MCP servers, enable OAuth2 & RBAC | `src/gateway/`, `src/worker/`, `src/mock-mcp-server/` | Covered |
| **5. Testing** | Functional, security, compliance, performance | `opa test src/policy` (functional/security/compliance at the policy layer) — automated in `.github/workflows/ci.yml` | Partial — **no load/performance testing**. Gap. |
| **6. Deployment** | Pilot → scale → monitor → handover | `example/` (Compose = single-cohort pilot shape; `example/k8s/` = the scale-out path); `docs/kubernetes.md` covers the NetworkPolicy that makes the Gateway a real boundary at scale | Covered |
| **7. Operations** | Monitor, manage, respond, improve | `audit_event` stdout logging = monitor. "Where to go next" in `workshop/BUILD-IT-YOURSELF.md` covers manage/improve (persist audit events, OPA sidecar) | Partial — **no incident-response runbook**. Gap. |
| **8. Retirement** | Decommission, retain, verify, close | — | **Not covered.** Nothing in the kit addresses decommissioning an agent or server, or audit-record retention after retirement. |

## Honest summary

Phases 2–4 and 6 are solid — that's the technical core this kit was built
to demonstrate. Phases 1, 5, and 7 are partially covered: the kit shows the
*shape* of the artifact (a catalog, a test suite, an audit log) without the
surrounding tooling a production rollout needs (a discovery scanner, load
tests, an incident runbook). Phase 8 isn't addressed at all.

If you're presenting the 8-phase playbook as the talk's throughline, it's
worth saying this out loud rather than implying the kit is a complete
implementation of all eight — "here's the reference implementation of
phases 2 through 4, here's the shape of 1, 5, and 7, phase 8 is on the
roadmap" is a more defensible claim to a room that will ask.

## Where to start filling gaps

- **Discovery tooling**: a script that queries OPA's own data API
  (`GET /v1/data/rbac/role_scopes`) and diffs it against what's actually
  reachable on the network would turn Phase 1 from "here's the config" into
  "here's what's *actually* out there, and here's the drift."
- **Performance testing**: `opa eval --profile` reports rule-level timing;
  wiring that into CI as a regression check is a natural Phase 5 addition.
- **Retirement**: the Rego policy already has the primitive you'd build
  this on — `data.gateway_config.safety_hold_agents` immediately denies
  everything for a given agent. A `retire_agent.sh` that adds an agent
  there *and* archives its `audit_event` history would cover Phase 8's
  "decommission" and "retain" in maybe 20 lines.
