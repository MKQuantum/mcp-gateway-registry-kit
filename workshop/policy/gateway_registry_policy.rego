package mcp.gateway.authz

# =============================================================================
# YOUR TASK: make `opa test .` pass 5/5.
#
# The test file (gateway_registry_policy_test.rego) is the specification.
# Read it first — it tells you exactly what behaviour is expected.
#
# Work in this order; run `opa test .` after each rule:
#   1. identity_verified      (given below as the worked example)
#   2. delegation_valid
#   3. rbac_scope_allowed
#   4. agbom_complete + attestation_chained  ->  provenance_valid
#   5. high_risk_action + step_up_required
#   6. decision               (the else-chain that ties it all together)
#   7. audit_event
#
# Input document shape you can rely on:
#
# input.agent.agent_id                          string
# input.agent.spiffe_id                         string, starts "spiffe://"
# input.agent.identity_token.verified           bool    (gateway verified it)
# input.agent.identity_token.exp                number  (unix seconds)
# input.agent.human_delegator                   string, "" if none
# input.agent.delegation_depth                  number
# input.agent.roles                             array of strings
# input.agent.agbom.model / .model_version      string
# input.agent.agbom.prompt_hash                 string
# input.agent.agbom.tool_manifest_hash          string
# input.agent.agbom.signature                   string
# input.agent.agbom.prev_attestation_hash       string, "" on a fresh session
# input.action.tool / .verb / .risk_tier        string
# input.context.process_instance_id             string
# input.context.business_key                    string
# input.context.human_attestation               bool
# input.context.timestamp                       string
#
# External data you can rely on:
# data.rbac.role_scopes[<role>]                 array of {tool, verb}
# data.gateway_config.max_delegation_depth      number
# data.gateway_config.safety_hold_agents        array of agent_id strings
# data.registry.last_attestation_hash[<agent>]  string (may be absent)
# =============================================================================


# -----------------------------------------------------------------------------
# GUARDRAIL 1 — Authorization & identity
# -----------------------------------------------------------------------------

# WORKED EXAMPLE — this one is done for you. Use it as the pattern.
# Note what it does NOT do: it doesn't verify a signature. The Gateway already
# did that. Policy consumes verified claims; it doesn't produce them.
identity_verified if {
	startswith(input.agent.spiffe_id, "spiffe://")
	input.agent.identity_token.verified == true
	input.agent.identity_token.exp > (time.now_ns() / 1000000000)
}

# TODO: delegation_valid
# Reads need no human. Any non-read verb needs a named human_delegator AND
# delegation_depth within data.gateway_config.max_delegation_depth.
# HINT: this is two separate rules with the same name — Rego ORs them.

# TODO: rbac_scope_allowed
# True if ANY of the agent's roles grants a scope matching this tool AND verb.
# HINT: `some role in input.agent.roles` then `some scope in data.rbac.role_scopes[role]`


# -----------------------------------------------------------------------------
# GUARDRAIL 2 — Provenance & attestation
# -----------------------------------------------------------------------------

# TODO: agbom_complete
# All five AgBOM fields (model, model_version, prompt_hash,
# tool_manifest_hash, signature) must be non-empty.

# TODO: attestation_chained
# The call's prev_attestation_hash must equal what the registry recorded for
# this agent. A fresh session (no registry entry) is also valid.
# HINT: again two rules — one for the match, one for `not data.registry...`

# TODO: provenance_valid
# agbom_complete AND attestation_chained


# -----------------------------------------------------------------------------
# GUARDRAIL 3 — Governance & policy
# -----------------------------------------------------------------------------

policy_version := "2.4.0"

# TODO: high_risk_action  — input.action.risk_tier == "high"

# TODO: step_up_required
# A high-risk action with no human attestation yet on the session.


# -----------------------------------------------------------------------------
# GUARDRAIL 4 — Audit & observability
# -----------------------------------------------------------------------------

# TODO: audit_event
# An object built from the decision + the input. Must include at minimum:
#   policy_version, agent_id, tool, verb, process_instance_id, business_key,
#   decision (= decision.allow), reason (= decision.reason), obligations,
#   timestamp
# Because it reads decision.allow, it's emitted for allows AND denies.


# -----------------------------------------------------------------------------
# DECISION — rule hierarchy: safety > security > contractual > organizational
# -----------------------------------------------------------------------------
#
# TODO: write the else-chain. First match wins; the final else is the only
# path to allow. Required order and exact reason strings:
#
#   1. agent in safety_hold_agents  -> deny "safety_hold"
#                                      obligations: notify_soc, suspend_agent_session
#   2. not identity_verified        -> deny "identity_not_verified"
#   3. not delegation_valid         -> deny "delegation_missing_for_write_action"
#   4. not provenance_valid         -> deny "provenance_incomplete_or_unchained"
#                                      obligations: quarantine_agent_session
#   5. not rbac_scope_allowed       -> deny "no_scope_grants_this_tool_and_verb"
#   6. step_up_required             -> deny "step_up_required"
#                                      obligations: require_human_approval,
#                                                   route_to_fluxnova_user_task
#   7. otherwise                    -> allow "granted_within_scope"
#                                      obligations: emit_attestation
#
# Shape: decision := {"allow": bool, "reason": string, "obligations": [string]}
#
# HINT for else-chain syntax in Rego v1:
#   decision := {...} if { cond } else := {...} if { cond } else := {...}
