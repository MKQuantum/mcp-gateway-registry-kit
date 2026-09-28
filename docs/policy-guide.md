# Policy guide

The whole pattern is downstream of one file: `src/policy/gateway_registry_policy.rego`.

| Guardrail | Rules | What it checks |
|---|---|---|
| 1. Authorization & identity | `identity_verified`, `delegation_valid`, `rbac_scope_allowed` | Signed identity, a named human behind every write, in-scope RBAC |
| 2. Provenance & attestation | `agbom_complete`, `attestation_chained` | Model/prompt/tool manifest present, and chained to the agent's last call — a Merkle-linked evidence graph, not unlinked log lines |
| 3. Governance & policy | the module itself, `policy_version` | One versioned file, same policy loaded by every gateway |
| 4. Audit & observability | `audit_event` | One evidence record per call — allow **or** deny |

**Design boundary worth preserving:** the policy never verifies a signature
itself. `identity_verified` checks `input.agent.identity_token.verified ==
true` — a claim the Gateway already established. Policy decides; it doesn't
authenticate. See `docs/architecture.md` for why that separation matters.

**Decision hierarchy** (first match wins):
`safety_hold` → `identity_not_verified` → `delegation_missing_for_write_action`
→ `provenance_incomplete_or_unchained` → `no_scope_grants_this_tool_and_verb`
→ `step_up_required` → `granted_within_scope`

Run the tests: `cd src/policy && opa test . -v` — expect `PASS: 5/5`.
Try a decision by hand:
`opa eval -i ../../example/sample-inputs/write-no-approval.json -d gateway_registry_policy.rego -d gateway_registry_data.json 'data.mcp.gateway.authz.decision' --format pretty`
