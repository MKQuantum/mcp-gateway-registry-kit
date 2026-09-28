package mcp.gateway.authz_test

import data.mcp.gateway.authz

base_agent := {
	"agent_id": "agt-trade-recon-01",
	"spiffe_id": "spiffe://fluxnova.bank.internal/agent/trade-recon",
	"identity_token": {"verified": true, "exp": 9999999999},
	"human_delegator": "",
	"delegation_depth": 0,
	"roles": ["trade-recon-agent"],
	"agbom": {
		"model": "claude-sonnet-4-6",
		"model_version": "2026-06-01",
		"prompt_hash": "sha256:aaa...",
		"tool_manifest_hash": "sha256:bbb...",
		"signature": "sig:ccc...",
		"prev_attestation_hash": "sha256:8f2e...c11a",
	},
}

base_context := {
	"process_instance_id": "proc-inst-7f21",
	"business_key": "TRD-2026-04471",
	"human_attestation": false,
	"timestamp": "2026-09-08T13:00:00Z",
}

# 1. Read-only ERP query, everything valid -> allow
test_allow_read_erp_query if {
	result := authz.decision with input as {
		"agent": base_agent,
		"action": {"tool": "erp.query", "verb": "read", "risk_tier": "low"},
		"context": base_context,
	}
		with data.rbac as {"role_scopes": {"trade-recon-agent": [{"tool": "erp.query", "verb": "read"}]}}
		with data.gateway_config as {"max_delegation_depth": 1, "safety_hold_agents": []}
		with data.registry as {"last_attestation_hash": {"agt-trade-recon-01": "sha256:8f2e...c11a"}}

	result.allow == true
	result.reason == "granted_within_scope"
}

# 2. High-risk trade correction, no human attestation on the session yet
#    -> denied, but routed to step-up / human approval, not a dead end
test_step_up_required_for_high_risk_write if {
	agent := object.union(base_agent, {"human_delegator": "trader.jsmith@bank.example", "delegation_depth": 1})

	result := authz.decision with input as {
		"agent": agent,
		"action": {"tool": "trade.correct", "verb": "write", "risk_tier": "high"},
		"context": base_context,
	}
		with data.rbac as {"role_scopes": {"trade-recon-agent": [{"tool": "trade.correct", "verb": "write"}]}}
		with data.gateway_config as {"max_delegation_depth": 1, "safety_hold_agents": []}
		with data.registry as {"last_attestation_hash": {"agt-trade-recon-01": "sha256:8f2e...c11a"}}

	result.allow == false
	result.reason == "step_up_required"
	"route_to_fluxnova_user_task" in result.obligations
}

# 3. Unverified identity token -> hard deny, never reaches RBAC or provenance
test_deny_unverified_identity if {
	agent := object.union(base_agent, {"identity_token": {"verified": false, "exp": 9999999999}})

	result := authz.decision with input as {
		"agent": agent,
		"action": {"tool": "erp.query", "verb": "read", "risk_tier": "low"},
		"context": base_context,
	}
		with data.rbac as {"role_scopes": {"trade-recon-agent": [{"tool": "erp.query", "verb": "read"}]}}
		with data.gateway_config as {"max_delegation_depth": 1, "safety_hold_agents": []}
		with data.registry as {"last_attestation_hash": {}}

	result.allow == false
	result.reason == "identity_not_verified"
}

# 4. Broken attestation chain (prev_attestation_hash doesn't match registry)
#    -> denied and the session is quarantined, not silently dropped
test_deny_broken_attestation_chain if {
	agent := object.union(base_agent, {"agbom": object.union(base_agent.agbom, {"prev_attestation_hash": "sha256:WRONG"})})

	result := authz.decision with input as {
		"agent": agent,
		"action": {"tool": "erp.query", "verb": "read", "risk_tier": "low"},
		"context": base_context,
	}
		with data.rbac as {"role_scopes": {"trade-recon-agent": [{"tool": "erp.query", "verb": "read"}]}}
		with data.gateway_config as {"max_delegation_depth": 1, "safety_hold_agents": []}
		with data.registry as {"last_attestation_hash": {"agt-trade-recon-01": "sha256:8f2e...c11a"}}

	result.allow == false
	result.reason == "provenance_incomplete_or_unchained"
	"quarantine_agent_session" in result.obligations
}

# 5. Safety hold beats everything, even a fully valid, in-scope read
test_safety_hold_overrides_everything if {
	result := authz.decision with input as {
		"agent": base_agent,
		"action": {"tool": "erp.query", "verb": "read", "risk_tier": "low"},
		"context": base_context,
	}
		with data.rbac as {"role_scopes": {"trade-recon-agent": [{"tool": "erp.query", "verb": "read"}]}}
		with data.gateway_config as {"max_delegation_depth": 1, "safety_hold_agents": ["agt-trade-recon-01"]}
		with data.registry as {"last_attestation_hash": {"agt-trade-recon-01": "sha256:8f2e...c11a"}}

	result.allow == false
	result.reason == "safety_hold"
}
