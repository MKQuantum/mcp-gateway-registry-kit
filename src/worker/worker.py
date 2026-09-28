"""
FluxNova External Task Worker (Python).

FluxNova ships a Java external-task client, but the external-task pattern is
just a REST contract — fetchAndLock / complete / handleBpmnError — so a Python
worker is a first-class citizen. That keeps the whole agent side of this stack
in Python.

What it does:
  - long-polls FluxNova for external tasks on topics "erp.query" and "trade.correct"
  - for each task, calls the Gateway (never the MCP server directly)
  - allow      -> complete the task with the tool result
  - step_up    -> raise BPMN error STEP_UP_REQUIRED, which the BPMN model
                  catches with a boundary event that opens a Tasklist user task
  - other deny -> handleFailure with the policy reason, so it surfaces as an
                  incident in Control Center rather than failing silently

Crucially, the human_delegator and business_key come from the *running process
instance*, not from config. That's the non-repudiation chain: every write
action is attributable to the person who started the process.
"""

import logging
import os
import time
from datetime import datetime, timedelta, timezone

import httpx
import jwt

FLUXNOVA_REST = os.environ.get("FLUXNOVA_REST", "http://fluxnova:8080/engine-rest")
GATEWAY_URL = os.environ.get("GATEWAY_URL", "http://gateway:8000")
JWT_SIGNING_SECRET = os.environ.get("JWT_SIGNING_SECRET", "dev-only-change-me")
WORKER_ID = os.environ.get("WORKER_ID", "python-worker-1")
AGENT_ID = os.environ.get("AGENT_ID", "agt-trade-recon-01")
AGENT_SPIFFE_ID = os.environ.get("AGENT_SPIFFE_ID", "spiffe://fluxnova.internal/agent/trade-recon")
MCP_SERVER_URL = os.environ.get("MCP_SERVER_URL", "http://mock-mcp:9000/mcp")
FLUXNOVA_USER = os.environ.get("FLUXNOVA_USER", "demo")
FLUXNOVA_PASSWORD = os.environ.get("FLUXNOVA_PASSWORD", "demo")

TOPICS = {
    "erp.query": {"verb": "read", "risk_tier": "low"},
    "trade.correct": {"verb": "write", "risk_tier": "high"},
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s")
log = logging.getLogger("worker")

auth = (FLUXNOVA_USER, FLUXNOVA_PASSWORD)


def mint_agent_token() -> str:
    """Short-lived, signed agent identity assertion. Replace with SPIRE-issued SVID in production."""
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {"spiffe_id": AGENT_SPIFFE_ID, "agent_id": AGENT_ID,
         "iat": now, "exp": now + timedelta(minutes=5)},
        JWT_SIGNING_SECRET, algorithm="HS256",
    )


def fetch_and_lock(client: httpx.Client) -> list[dict]:
    body = {
        "workerId": WORKER_ID,
        "maxTasks": 5,
        "usePriority": True,
        "asyncResponseTimeout": 10000,   # long-poll
        "topics": [
            {"topicName": t, "lockDuration": 30000,
             "variables": ["businessKey", "startUserId", "humanAttestation", "correctionAmount"]}
            for t in TOPICS
        ],
    }
    r = client.post(f"{FLUXNOVA_REST}/external-task/fetchAndLock", json=body, auth=auth, timeout=30.0)
    r.raise_for_status()
    return r.json()


def var(task: dict, name: str, default=None):
    v = task.get("variables", {}).get(name)
    return v["value"] if v and "value" in v else default


def handle_task(client: httpx.Client, task: dict) -> None:
    topic = task["topicName"]
    meta = TOPICS[topic]
    task_id = task["id"]
    business_key = var(task, "businessKey", task.get("businessKey") or "")
    start_user = var(task, "startUserId", "") or ""
    human_attested = bool(var(task, "humanAttestation", False))

    payload = {
        "agent_id": AGENT_ID,
        "roles": ["trade-recon-agent"],
        "tool": topic,
        "verb": meta["verb"],
        "risk_tier": meta["risk_tier"],
        "mcp_server_url": MCP_SERVER_URL,
        "arguments": (
            {"business_key": business_key}
            if topic == "erp.query"
            else {"business_key": business_key, "amount": int(var(task, "correctionAmount", 0) or 0)}
        ),
        "process_instance_id": task["processInstanceId"],
        "business_key": business_key,
        # a named human is required by policy for any write
        "human_delegator": start_user if meta["verb"] != "read" else "",
        "delegation_depth": 1 if meta["verb"] != "read" else 0,
        "human_attestation": human_attested,
    }

    resp = client.post(
        f"{GATEWAY_URL}/v1/invoke", json=payload,
        headers={"Authorization": f"Bearer {mint_agent_token()}"}, timeout=30.0,
    )
    resp.raise_for_status()
    decision = resp.json()

    log.info("task=%s topic=%s allowed=%s reason=%s",
             task_id, topic, decision["allowed"], decision["reason"])

    if decision["allowed"]:
        client.post(
            f"{FLUXNOVA_REST}/external-task/{task_id}/complete",
            json={"workerId": WORKER_ID,
                  "variables": {"mcpResult": {"value": str(decision["result"]), "type": "String"},
                                "policyReason": {"value": decision["reason"], "type": "String"}}},
            auth=auth, timeout=15.0,
        ).raise_for_status()
        return

    if "route_to_fluxnova_user_task" in decision["obligations"]:
        # Don't fail — hand control back to the process, which routes to Tasklist.
        client.post(
            f"{FLUXNOVA_REST}/external-task/{task_id}/bpmnError",
            json={"workerId": WORKER_ID, "errorCode": "STEP_UP_REQUIRED",
                  "errorMessage": decision["reason"],
                  "variables": {"policyReason": {"value": decision["reason"], "type": "String"}}},
            auth=auth, timeout=15.0,
        ).raise_for_status()
        return

    client.post(
        f"{FLUXNOVA_REST}/external-task/{task_id}/failure",
        json={"workerId": WORKER_ID, "errorMessage": decision["reason"],
              "errorDetails": str(decision["obligations"]), "retries": 0, "retryTimeout": 0},
        auth=auth, timeout=15.0,
    ).raise_for_status()


def main() -> None:
    log.info("worker starting: fluxnova=%s gateway=%s", FLUXNOVA_REST, GATEWAY_URL)
    with httpx.Client() as client:
        while True:
            try:
                for task in fetch_and_lock(client):
                    handle_task(client, task)
            except Exception as e:  # keep the worker alive across transient errors
                log.warning("poll error: %s", e)
                time.sleep(5)


if __name__ == "__main__":
    main()
