"""
Gateway Registry — enforcement point (PEP).

Sits between the FluxNova External Task Worker and the real MCP servers.
For every tool invocation it:
  1. verifies the caller's signed identity (JWT — swap for SPIFFE/mTLS in production)
  2. builds the OPA input document and calls the policy decision point (PDP)
  3. on allow: makes the real MCP call, records the new attestation hash, returns the result
  4. on deny / step_up: does NOT call the MCP server; returns the decision + obligations
  5. emits one structured audit_event per call, allow or deny, to stdout

Run locally:  uvicorn app:app --host 0.0.0.0 --port 8000
"""

import hashlib
import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any

import httpx
import jwt
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

# --------------------------------------------------------------------------
# Config (all overridable via env vars — see k8s/04-gateway.yaml)
# --------------------------------------------------------------------------
OPA_URL = os.environ.get("OPA_URL", "http://opa:8181")
OPA_DECISION_PATH = "/v1/data/mcp/gateway/authz/decision"
JWT_SIGNING_SECRET = os.environ.get("JWT_SIGNING_SECRET", "dev-only-change-me")
JWT_ALGORITHM = "HS256"
AGENT_MODEL = os.environ.get("AGENT_MODEL", "claude-sonnet-4-6")
AGENT_MODEL_VERSION = os.environ.get("AGENT_MODEL_VERSION", "2026-06-01")

logging.basicConfig(level=logging.INFO, format="%(message)s")
audit_logger = logging.getLogger("audit")

app = FastAPI(title="Gateway Registry — Policy Enforcement Point")
http_client = httpx.AsyncClient(timeout=10.0)

# In-memory chain-hash store for the demo. In production this is a real
# table (or OPA's own bundle-backed data store) keyed by agent_id.
_last_attestation_hash: dict[str, str] = {}


# --------------------------------------------------------------------------
# Request / response models
# --------------------------------------------------------------------------
class InvokeRequest(BaseModel):
    agent_id: str
    roles: list[str]
    tool: str                      # e.g. "erp.query", "trade.correct"
    verb: str                      # "read" | "write"
    risk_tier: str = "low"         # "low" | "high"
    mcp_server_url: str            # where the real MCP server lives
    arguments: dict[str, Any] = {}
    process_instance_id: str
    business_key: str
    human_delegator: str = ""
    delegation_depth: int = 0
    human_attestation: bool = False


class InvokeResponse(BaseModel):
    allowed: bool
    reason: str
    obligations: list[str]
    result: Any = None
    audit_event: dict[str, Any]


# --------------------------------------------------------------------------
# Identity verification (Guardrail 1)
# --------------------------------------------------------------------------
def verify_identity(authorization: str | None) -> dict[str, Any]:
    """
    Verifies the bearer JWT the worker presents on behalf of the agent.
    This is the piece the Rego policy explicitly does NOT do itself —
    identity_verified in gateway_registry_policy.rego trusts this claim,
    it does not re-check the signature.

    Swap this function for real SPIFFE/SPIRE or mTLS client-cert
    verification in production; the interface (return a dict with
    spiffe_id + verified + exp) stays the same either way.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "missing bearer token")
    token = authorization.removeprefix("Bearer ")
    try:
        claims = jwt.decode(token, JWT_SIGNING_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError as e:
        raise HTTPException(401, f"invalid token: {e}")
    return {
        "spiffe_id": claims.get("spiffe_id", ""),
        "verified": True,
        "exp": claims.get("exp", 0),
    }


# --------------------------------------------------------------------------
# AgBOM construction (Guardrail 2) — chained, not just signed
# --------------------------------------------------------------------------
def build_agbom(agent_id: str) -> dict[str, str]:
    prompt_hash = "sha256:" + hashlib.sha256(b"trade-reconciliation-worker-v1").hexdigest()[:12]
    tool_manifest_hash = "sha256:" + hashlib.sha256(b"erp.query,trade.correct").hexdigest()[:12]
    prev_hash = _last_attestation_hash.get(agent_id, "")
    return {
        "model": AGENT_MODEL,
        "model_version": AGENT_MODEL_VERSION,
        "prompt_hash": prompt_hash,
        "tool_manifest_hash": tool_manifest_hash,
        "signature": "sig:" + hashlib.sha256(
            f"{agent_id}{prompt_hash}{tool_manifest_hash}".encode()
        ).hexdigest()[:16],
        "prev_attestation_hash": prev_hash,
    }


def next_attestation_hash(agbom: dict[str, str], action: dict[str, str]) -> str:
    material = json.dumps(agbom, sort_keys=True) + json.dumps(action, sort_keys=True)
    return "sha256:" + hashlib.sha256(material.encode()).hexdigest()[:12]


# --------------------------------------------------------------------------
# OPA call (the policy decision point)
# --------------------------------------------------------------------------
async def evaluate_policy(opa_input: dict[str, Any]) -> dict[str, Any]:
    resp = await http_client.post(OPA_URL + OPA_DECISION_PATH, json={"input": opa_input})
    resp.raise_for_status()
    return resp.json()["result"]


async def push_attestation_hash(agent_id: str, new_hash: str) -> None:
    """Updates OPA's data store so the NEXT call's attestation_chained check has something to compare against."""
    await http_client.put(f"{OPA_URL}/v1/data/registry/last_attestation_hash/{agent_id}", json=new_hash)
    _last_attestation_hash[agent_id] = new_hash


# --------------------------------------------------------------------------
# Real MCP call (only reached on allow)
# --------------------------------------------------------------------------
async def call_mcp_tool(server_url: str, tool: str, arguments: dict[str, Any]) -> Any:
    """
    Minimal MCP client call over Streamable HTTP. Uses the official `mcp`
    SDK's client session — a fresh session per call, which is simple and
    correct for a reference implementation. Pool/reuse sessions in
    production if call volume warrants it.
    """
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    async with streamablehttp_client(server_url) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool, arguments)
            return [c.model_dump() for c in result.content]


# --------------------------------------------------------------------------
# Main endpoint
# --------------------------------------------------------------------------
@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.post("/v1/invoke", response_model=InvokeResponse)
async def invoke(req: InvokeRequest, authorization: str | None = Header(default=None)):
    identity = verify_identity(authorization)
    agbom = build_agbom(req.agent_id)

    opa_input = {
        "agent": {
            "agent_id": req.agent_id,
            "spiffe_id": identity["spiffe_id"],
            "identity_token": {"verified": identity["verified"], "exp": identity["exp"]},
            "human_delegator": req.human_delegator,
            "delegation_depth": req.delegation_depth,
            "roles": req.roles,
            "agbom": agbom,
        },
        "action": {"tool": req.tool, "verb": req.verb, "risk_tier": req.risk_tier},
        "context": {
            "process_instance_id": req.process_instance_id,
            "business_key": req.business_key,
            "human_attestation": req.human_attestation,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    }

    decision = await evaluate_policy(opa_input)

    audit_event = {
        "agent_id": req.agent_id,
        "spiffe_id": identity["spiffe_id"],
        "model": agbom["model"],
        "model_version": agbom["model_version"],
        "tool": req.tool,
        "verb": req.verb,
        "process_instance_id": req.process_instance_id,
        "business_key": req.business_key,
        "decision": decision["allow"],
        "reason": decision["reason"],
        "obligations": decision["obligations"],
        "prev_attestation_hash": agbom["prev_attestation_hash"],
        "timestamp": opa_input["context"]["timestamp"],
    }
    audit_logger.info(json.dumps({"audit_event": audit_event}))

    if not decision["allow"]:
        return InvokeResponse(
            allowed=False, reason=decision["reason"], obligations=decision["obligations"],
            result=None, audit_event=audit_event,
        )

    result = await call_mcp_tool(req.mcp_server_url, req.tool, req.arguments)

    new_hash = next_attestation_hash(agbom, {"tool": req.tool, "verb": req.verb, "ts": audit_event["timestamp"]})
    await push_attestation_hash(req.agent_id, new_hash)
    audit_event["new_attestation_hash"] = new_hash

    return InvokeResponse(
        allowed=True, reason=decision["reason"], obligations=decision["obligations"],
        result=result, audit_event=audit_event,
    )
