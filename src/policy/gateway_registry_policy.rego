package mcp.gateway.authz

# =============================================================================
# Gateway Registry — Portable Policy (OPA / Rego)
#
# One policy, loaded by every Gateway / PDP sidecar in the MCP mesh, closing
# the four guardrail gaps called out for the Guardrails industry layer:
#
#   1. Authorization & identity   -> identity_verified, delegation_valid,
#                                     rbac_scope_allowed
#   2. Provenance & attestation   -> agbom_complete, attestation_chained
#   3. Governance & policy        -> this file itself: one portable module,
#                                     versioned and unit-tested, instead of
#                                     per-firm gateway config
#   4. Audit & observability      -> audit_event, emitted for every call,
#                                     allowed or denied
#
# Decision hierarchy (matches the "Agentic Shoulds" ordering referenced for
# Guardrail 2): safety > security > contractual > organizational.
# =============================================================================

# ---------------------------------------------------------------------------
# GUARDRAIL 1 — Authorization & Identity
# "Who is this agent, what may it do." Includes agent identities, human-to-
# agent delegation, fine-grained auth.
# ---------------------------------------------------------------------------

# An agent principal, not a shared API key: a live SPIFFE ID plus a signed,
# unexpired identity assertion (verified upstream by the gateway's mTLS/JWT
# layer — OPA trusts the verified claim, it does not re-check the signature).
identity_verified if {
	startswith(input.agent.spiffe_id, "spiffe://")
	input.agent.identity_token.verified == true
	input.agent.identity_token.exp > time.now_ns() / 1000000000
}

# Reads need no human in the loop. Any write / correction / execution verb
# must carry a named human delegator and stay within the allowed delegation
# depth — this is the non-repudiation chain: "you can't sue the agent, but
# you can always name the human who authorized it."
delegation_valid if {
	input.action.verb == "read"
}

delegation_valid if {
	input.action.verb != "read"
	input.agent.human_delegator != ""
	input.agent.delegation_depth <= data.gateway_config.max_delegation_depth
}

# Fine-grained, time-bound RBAC evaluated against a versioned scope table —
# not a static, all-or-nothing API key.
rbac_scope_allowed if {
	some role in input.agent.roles
	some scope in data.rbac.role_scopes[role]
	scope.tool == input.action.tool
	scope.verb == input.action.verb
}

# ---------------------------------------------------------------------------
# GUARDRAIL 2 — Provenance & Attestation
# "Prove which model, skill, server produced an output." No shared standard
# for signing or chaining exists today — this section is that standard.
# ---------------------------------------------------------------------------

# Minimum viable AgBOM: model identity, prompt/skill version, tool manifest,
# and a signature over all of it.
agbom_complete if {
	input.agent.agbom.model != ""
	input.agent.agbom.model_version != ""
	input.agent.agbom.prompt_hash != ""
	input.agent.agbom.tool_manifest_hash != ""
	input.agent.agbom.signature != ""
}

# Chaining, not just signing: this call's AgBOM must reference the hash of
# the agent's last attested call, so the evidence trail is a Merkle-linked
# graph, not a pile of unlinked log lines.
attestation_chained if {
	last := data.registry.last_attestation_hash[input.agent.agent_id]
	input.agent.agbom.prev_attestation_hash == last
}

# A fresh session has no prior call to chain to.
attestation_chained if {
	not data.registry.last_attestation_hash[input.agent.agent_id]
}

provenance_valid if {
	agbom_complete
	attestation_chained
}

# ---------------------------------------------------------------------------
# GUARDRAIL 3 — Governance & Policy
# "Express constraints once, enforce everywhere." Gateways and allow-lists
# exist as products today; this module is the portable policy language that
# sits underneath any of them.
# ---------------------------------------------------------------------------

policy_version := "2.4.0"

high_risk_action if {
	input.action.risk_tier == "high"
}

# Just-in-time elevation: a high-risk verb without a live human attestation
# already recorded on the session is not rejected outright — it is routed
# to a step-up obligation instead. See Guardrail 2 (dynamic RBAC) reference
# architecture: "Tool B (blocked, pending human approval)."
step_up_required if {
	high_risk_action
	not input.context.human_attestation
}

# ---------------------------------------------------------------------------
# GUARDRAIL 4 — Audit & Observability
# "Reconstruct what the agent did, to a regulator's bar." Every call —
# allowed or denied — produces one evidence record.
# ---------------------------------------------------------------------------

audit_event := {
	"policy_version": policy_version,
	"agent_id": input.agent.agent_id,
	"spiffe_id": input.agent.spiffe_id,
	"model": input.agent.agbom.model,
	"model_version": input.agent.agbom.model_version,
	"prompt_hash": input.agent.agbom.prompt_hash,
	"tool": input.action.tool,
	"verb": input.action.verb,
	"process_instance_id": input.context.process_instance_id,
	"business_key": input.context.business_key,
	"decision": decision.allow,
	"reason": decision.reason,
	"obligations": decision.obligations,
	"prev_attestation_hash": input.agent.agbom.prev_attestation_hash,
	"timestamp": input.context.timestamp,
}

# ---------------------------------------------------------------------------
# Decision — rule hierarchy: safety > security > contractual > organizational
# First matching clause wins; the final clause is the only path to "allow".
# ---------------------------------------------------------------------------

decision := {"allow": false, "reason": "safety_hold", "obligations": ["notify_soc", "suspend_agent_session"]} if {
	input.agent.agent_id in data.gateway_config.safety_hold_agents
} else := {"allow": false, "reason": "identity_not_verified", "obligations": []} if {
	not identity_verified
} else := {"allow": false, "reason": "delegation_missing_for_write_action", "obligations": []} if {
	not delegation_valid
} else := {"allow": false, "reason": "provenance_incomplete_or_unchained", "obligations": ["quarantine_agent_session"]} if {
	not provenance_valid
} else := {"allow": false, "reason": "no_scope_grants_this_tool_and_verb", "obligations": []} if {
	not rbac_scope_allowed
} else := {"allow": false, "reason": "step_up_required", "obligations": ["require_human_approval", "route_to_fluxnova_user_task"]} if {
	step_up_required
} else := {"allow": true, "reason": "granted_within_scope", "obligations": ["emit_attestation"]}
