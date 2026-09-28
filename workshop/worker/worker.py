"""
PART 5 — FluxNova External Task Worker.

FluxNova ships a Java client, but external tasks are just a REST contract,
so Python works fine and keeps the agent side in one language.

YOUR TASK: a polling loop that:

  1. long-polls POST {REST}/external-task/fetchAndLock for topics
     "erp.query" and "trade.correct"
  2. for each task, builds a Gateway request and POSTs it to /v1/invoke
     with a freshly minted agent JWT
  3. routes the outcome back into the process:
       allowed                              -> POST .../complete
       obligations has route_to_fluxnova_user_task
                                            -> POST .../bpmnError
                                               errorCode STEP_UP_REQUIRED
       any other deny                       -> POST .../failure
  4. never crashes on a transient error — wrap the loop body

THE POINT OF THIS PART:
  human_delegator and business_key come from the RUNNING PROCESS INSTANCE,
  not from config. That's the non-repudiation chain — every write traces to
  a named human who started the process. Read them out of task variables.

CHECKPOINT: with the stack up, start a process and watch the worker log one
line per task with the policy's decision.

FluxNova REST reference:
  POST {REST}/external-task/fetchAndLock
       {"workerId","maxTasks","asyncResponseTimeout",
        "topics":[{"topicName","lockDuration","variables":[...]}]}
  POST {REST}/external-task/{id}/complete   {"workerId","variables"}
  POST {REST}/external-task/{id}/bpmnError  {"workerId","errorCode","errorMessage"}
  POST {REST}/external-task/{id}/failure    {"workerId","errorMessage","retries"}
  (basic auth: demo/demo)
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
MCP_SERVER_URL = os.environ.get("MCP_SERVER_URL", "http://mock-mcp:9000/mcp")
AGENT_ID = os.environ.get("AGENT_ID", "agt-trade-recon-01")
AGENT_SPIFFE_ID = os.environ.get("AGENT_SPIFFE_ID", "spiffe://fluxnova.internal/agent/trade-recon")

# Map each topic to the risk profile the policy will evaluate.
TOPICS = {
    "erp.query": {"verb": "read", "risk_tier": "low"},
    "trade.correct": {"verb": "write", "risk_tier": "high"},
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s")
log = logging.getLogger("worker")


def mint_agent_token() -> str:
    """TODO: short-lived HS256 JWT carrying spiffe_id + agent_id. ~5 min expiry."""
    raise NotImplementedError


def fetch_and_lock(client: httpx.Client) -> list[dict]:
    """TODO: long-poll FluxNova for tasks on both topics.
    Ask for variables: businessKey, startUserId, humanAttestation, correctionAmount."""
    raise NotImplementedError


def var(task: dict, name: str, default=None):
    """TODO: FluxNova wraps variables as {"value":..., "type":...}. Unwrap safely."""
    raise NotImplementedError


def handle_task(client: httpx.Client, task: dict) -> None:
    """TODO: build the Gateway payload, call it, then complete / bpmnError / failure."""
    raise NotImplementedError


def main() -> None:
    """TODO: loop forever — fetch_and_lock, handle each task, survive errors."""
    raise NotImplementedError


if __name__ == "__main__":
    main()
