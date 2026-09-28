"""
PART 3 — The Gateway (Policy Enforcement Point).

This is the heart of the pattern. Everything routes through here; nothing
talks to an MCP server directly.

YOUR TASK: a FastAPI service exposing POST /v1/invoke that, per call:

  1. verifies the caller's bearer JWT           -> verify_identity()
  2. builds an AgBOM for this agent             -> build_agbom()
  3. POSTs {"input": ...} to OPA and reads the decision
  4. emits ONE audit event to stdout — allow or deny, always
  5. if denied: return the decision. DO NOT call the MCP server.
  6. if allowed: call the real MCP tool, record the new attestation hash,
     return the result

THE KEY ARCHITECTURAL RULE:
  Signature/attestation verification happens HERE, in Python.
  OPA only decides based on claims you have already verified.
  Don't blur that boundary — it's what makes the policy portable.

CHECKPOINT: `curl localhost:8000/healthz` returns {"status":"ok"}, and a
POST to /v1/invoke with a bad token returns 401.

OPA endpoints you'll need:
  POST {OPA_URL}/v1/data/mcp/gateway/authz/decision   body {"input": {...}}
       -> {"result": {"allow":..., "reason":..., "obligations":[...]}}
  PUT  {OPA_URL}/v1/data/registry/last_attestation_hash/{agent_id}
       body: a bare JSON string. Returns 204.
"""

import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

import httpx
import jwt
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

OPA_URL = os.environ.get("OPA_URL", "http://opa:8181")
OPA_DECISION_PATH = "/v1/data/mcp/gateway/authz/decision"
JWT_SIGNING_SECRET = os.environ.get("JWT_SIGNING_SECRET", "dev-only-change-me")

logging.basicConfig(level=logging.INFO, format="%(message)s")
audit_logger = logging.getLogger("audit")

app = FastAPI(title="Gateway Registry — Policy Enforcement Point")
http_client = httpx.AsyncClient(timeout=10.0)

# Demo-only chain store. Production: a real table.
_last_attestation_hash: dict[str, str] = {}


class InvokeRequest(BaseModel):
    """TODO: fields the worker sends. See PART 5 for what it will send."""
    # agent_id, roles, tool, verb, risk_tier, mcp_server_url, arguments,
    # process_instance_id, business_key, human_delegator, delegation_depth,
    # human_attestation
    pass


class InvokeResponse(BaseModel):
    """TODO: allowed, reason, obligations, result, audit_event"""
    pass


def verify_identity(authorization: str | None) -> dict[str, Any]:
    """
    TODO: reject anything without a "Bearer " prefix (401).
    Decode+verify the JWT with JWT_SIGNING_SECRET / HS256.
    Return {"spiffe_id": ..., "verified": True, "exp": ...}.

    Keep this function small and isolated — swapping it for SPIFFE/SPIRE
    later should not touch anything else.
    """
    raise NotImplementedError


def build_agbom(agent_id: str) -> dict[str, str]:
    """
    TODO: return model, model_version, prompt_hash, tool_manifest_hash,
    signature, and prev_attestation_hash (from _last_attestation_hash,
    "" if this agent hasn't called before).

    Hashing static strings is fine to start. Making this real —
    actual prompt digest, real tool manifest — is an extension exercise.
    """
    raise NotImplementedError


def next_attestation_hash(agbom: dict[str, str], action: dict[str, str]) -> str:
    """TODO: deterministic hash over agbom + action. This is the chain link."""
    raise NotImplementedError


async def evaluate_policy(opa_input: dict[str, Any]) -> dict[str, Any]:
    """TODO: POST to OPA, return response.json()["result"]."""
    raise NotImplementedError


async def push_attestation_hash(agent_id: str, new_hash: str) -> None:
    """TODO: PUT the hash into OPA's data store so the NEXT call can chain to it."""
    raise NotImplementedError


async def call_mcp_tool(server_url: str, tool: str, arguments: dict[str, Any]) -> Any:
    """
    TODO: call the real MCP tool. Only reached on allow.

    HINT:
      from mcp import ClientSession
      from mcp.client.streamable_http import streamablehttp_client
      async with streamablehttp_client(server_url) as (read, write, _):
          async with ClientSession(read, write) as session:
              await session.initialize()
              result = await session.call_tool(tool, arguments)
    """
    raise NotImplementedError


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.post("/v1/invoke")
async def invoke(req: InvokeRequest, authorization: str | None = Header(default=None)):
    """
    TODO: orchestrate the six steps from the docstring at the top.

    Watch the ordering: emit the audit event BEFORE returning on a deny,
    or your denials won't be in the evidence trail — which defeats the point.
    """
    raise NotImplementedError
