# Architecture

> Adapted from the MCP Dev Summit Toronto talk companion notes.

FluxNova (`finos/fluxnova-bpm-platform`) is the open-source BPMN 2.0 process
engine incubating at FINOS, built on the Camunda 7 engine lineage. It ships
an embeddable engine, a REST API, an External Task Client
(`org.finos.fluxnova.bpm.client`), Tasklist for human work, and Admin for
users/groups/authorizations. That combination — a durable process instance
that already tracks *who* is doing *what* *on whose behalf* — is exactly the
context the Gateway Registry policy needs on every decision. This doc maps
the four guardrails to concrete FluxNova touchpoints and walks through one
worked example end to end.

## 1. Guardrail → Policy → FluxNova touchpoint

| Guardrail (from the industry-layer slide) | Enforced by | FluxNova touchpoint |
|---|---|---|
| **Authorization & identity** — who is this agent, what may it do | `identity_verified`, `delegation_valid`, `rbac_scope_allowed` in `src/policy/gateway_registry_policy.rego` | The External Task Worker signs its identity assertion using the process engine's authenticated service identity; `human_delegator` is populated from the process's `startUserId` / task assignee, giving every write action a named human |
| **Provenance & attestation** — prove which model, skill, server produced an output | `agbom_complete`, `attestation_chained` | The worker attaches an AgBOM built from the LLM call metadata (model, prompt hash, tool manifest) plus the **process definition key + version** as an additional provenance field — the BPMN model is itself a versioned artifact |
| **Governance & policy** — express constraints once, enforce everywhere | The whole `.rego` module, loaded once by the Gateway's OPA sidecar | Every BPMN process in the FluxNova install — trade reconciliation, KYC refresh, collateral substitution — calls the *same* gateway, so the same policy governs all of them without per-process config |
| **Audit & observability** — reconstruct what the agent did, to a regulator's bar | `audit_event`, emitted on every call | Each `audit_event` carries `process_instance_id` and `business_key`, so a regulator's question about trade `TRD-2026-04471` joins directly to FluxNova's own history tables and Control Center timeline — one query, not a cross-system reconciliation exercise |

## 2. Worked example: the trade reconciliation process

This mirrors the reference architecture from the talk. A `Trade
Reconciliation` BPMN process has two service tasks implemented as FluxNova
external tasks:

1. **`Query ERP Balances`** (topic `erp.query`, read) — the agent reads GL
   entries to compare against the trade blotter.
2. **`Initiate Correction`** (topic `trade.correct`, write) — triggered only
   if a variance is found; this is the $50M-variance moment from the talk.

Both tasks route through the same Gateway → OPA call before the worker is
allowed to touch the underlying MCP server. Below are the **actual verified
outputs** from running `src/policy/gateway_registry_policy.rego` (via `opa eval`)
against realistic inputs for each task:

**Task 1 — `erp.query`, read, low risk:**
```json
{ "allow": true, "reason": "granted_within_scope", "obligations": ["emit_attestation"] }
```

**Task 2 — `trade.correct`, write, high risk, no human attestation on the session yet:**
```json
{
  "allow": false,
  "reason": "step_up_required",
  "obligations": ["require_human_approval", "route_to_fluxnova_user_task"]
}
```

The `route_to_fluxnova_user_task` obligation is the hook back into FluxNova:
instead of completing the external task, the worker raises a BPMN error,
which the process definition catches with a boundary event that creates a
**Tasklist** user task assigned to the `traders` candidate group. A human
trader approves or rejects in Tasklist; on approval, the process
re-attempts the same MCP call with `human_attestation: true` in context,
which now clears `step_up_required` and the write proceeds — with its own
`audit_event` chained to the first.

## 3. External Task Worker (Java)

Illustrative worker using FluxNova's external task client. It calls the
Gateway (which evaluates the OPA policy and proxies to the MCP server on
`allow`) instead of calling the MCP server directly:

```java
import org.finos.fluxnova.bpm.client.ExternalTaskClient;
import org.finos.fluxnova.bpm.client.task.ExternalTask;
import org.finos.fluxnova.bpm.client.task.ExternalTaskHandler;
import org.finos.fluxnova.bpm.client.task.ExternalTaskService;

public class TradeCorrectionWorker {

    public static void main(String[] args) {
        ExternalTaskClient client = ExternalTaskClient.create()
            .baseUrl("http://fluxnova-engine:8080/engine-rest")
            .asyncResponseTimeout(10000)
            .build();

        client.subscribe("trade.correct")
            .lockDuration(30000)
            .handler(new ExternalTaskHandler() {
                @Override
                public void execute(ExternalTask task, ExternalTaskService svc) {

                    // Build the gateway request from process + agent context.
                    // human_delegator comes straight from the running instance,
                    // not from a config file — that's the non-repudiation chain.
                    GatewayRequest req = GatewayRequest.builder()
                        .agentId("agt-trade-recon-01")
                        .humanDelegator(task.getVariable("startUserId"))
                        .delegationDepth(1)
                        .tool("trade.correct")
                        .verb("write")
                        .riskTier("high")
                        .processInstanceId(task.getProcessInstanceId())
                        .businessKey(task.getBusinessKey())
                        .humanAttestation(task.getVariable("humanAttestation"))
                        .build();

                    GatewayResponse resp = gateway.evaluate(req); // -> OPA decision

                    if (!resp.isAllowed() && resp.getObligations()
                            .contains("route_to_fluxnova_user_task")) {
                        // Don't complete the task — hand it to a human via a
                        // BPMN error boundary event caught by a User Task
                        // in the "traders" candidate group (Tasklist).
                        svc.handleBpmnError(task, "STEP_UP_REQUIRED",
                            "Gateway requires human trader approval");
                        return;
                    }

                    if (!resp.isAllowed()) {
                        svc.handleFailure(task, resp.getReason(),
                            resp.getReason(), 0, 0L);
                        return;
                    }

                    // Allowed: the gateway has already proxied the call and
                    // returned the MCP tool result plus the audit_event id.
                    svc.complete(task, resp.getResultVariables());
                }
            })
            .open();
    }
}
```

## 4. Reference architecture (see accompanying slide)

```
 Financial Analyst
        │
        ▼
 FluxNova Tasklist ──(approve/reject)──┐
        ▲                              │
        │ user task on step-up          │
        │                              ▼
 FluxNova Engine (BPMN) ──ext. task──▶ Gateway Registry
  process instance,                    ├─ Identity verifier (SPIFFE/JWT)
  business key, history                ├─ OPA PDP (gateway_registry_policy.rego)
                                        ├─ AgBOM attestation generator
                                        └─ Audit / evidence store ──▶ Regulator export
                                                │
                                                ▼
                                        MCP Servers
                                   Market Data · Risk · ERP · Trade Execution
```

Every arrow that crosses the Gateway box is governed by the same policy
file — that is the "portable policy language" the guardrails slide says
doesn't exist yet in most shops today.
