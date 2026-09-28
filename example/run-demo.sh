#!/usr/bin/env bash
# Deploys the BPMN model to FluxNova, starts a trade-reconciliation instance,
# and shows the allow / step-up decisions flowing through.
#
# Prereq — EITHER:
#   Docker Compose:  docker compose up --build     (then just run this)
#   Kubernetes:      ./deploy.sh, plus port-forwards:
#                      kubectl -n mcp-gov port-forward svc/fluxnova 8080:8080 &
#                      kubectl -n mcp-gov port-forward svc/gateway  8000:8000 &
set -Eeuo pipefail

REST=${REST:-http://localhost:8080/engine-rest}
AUTH=${AUTH:-demo:demo}
BK="TRD-2026-04471"

echo "==> Deploying BPMN model"
curl -sS -u "$AUTH" -X POST "$REST/deployment/create" \
  -F "deployment-name=trade-reconciliation" \
  -F "enable-duplicate-filtering=true" \
  -F "deploy-changed-only=true" \
  -F "trade-reconciliation.bpmn=@../src/bpmn/trade-reconciliation.bpmn" \
  | python3 -m json.tool | head -20

echo
echo "==> Starting a process instance for $BK"
curl -sS -u "$AUTH" -X POST \
  "$REST/process-definition/key/trade-reconciliation/start" \
  -H 'Content-Type: application/json' \
  -d "{
        \"businessKey\": \"$BK\",
        \"variables\": {
          \"businessKey\":      {\"value\": \"$BK\", \"type\": \"String\"},
          \"startUserId\":      {\"value\": \"trader.jsmith@bank.example\", \"type\": \"String\"},
          \"correctionAmount\": {\"value\": 50000000, \"type\": \"Long\"},
          \"humanAttestation\": {\"value\": false, \"type\": \"Boolean\"}
        }
      }" | python3 -m json.tool

echo
echo "==> Waiting for the worker to process both tasks..."
sleep 12

echo
echo "==> Gateway audit trail (allow on read, step-up on write):"
# Works whether you started the stack with Docker Compose or Kubernetes.
if docker compose ps >/dev/null 2>&1 && [ -n "$(docker compose ps -q gateway 2>/dev/null)" ]; then
  docker compose logs gateway --tail=40 2>/dev/null | grep audit_event || true
elif command -v kubectl >/dev/null 2>&1; then
  kubectl -n mcp-gov logs deploy/gateway --tail=40 2>/dev/null | grep audit_event || true
else
  echo "    (couldn't find gateway logs — check 'docker compose logs gateway')"
fi

echo
echo "==> Open user tasks (the step-up landed in Tasklist):"
curl -sS -u "$AUTH" "$REST/task?processDefinitionKey=trade-reconciliation" \
  | python3 -m json.tool | head -30

cat <<'DONE'

============================================================
  What just happened:

    erp.query     -> allow / granted_within_scope    (read, low risk)
    trade.correct -> deny  / step_up_required        (write, high risk)
                     -> BPMN error -> Tasklist user task for group "traders"

  To complete the approval and let the write through:

    1. Open http://localhost:8080/ and log in
    2. Go to Tasklist, claim "Trader approval required"
    3. Tick "I approve this correction" and complete the task
    4. The worker retries trade.correct with humanAttestation=true,
       policy returns allow, and the correction books.

  Watch the approved decision land:
    docker compose logs gateway | grep audit_event         (Docker Compose)
    kubectl -n mcp-gov logs -f deploy/gateway | grep audit_event   (Kubernetes)
============================================================
DONE
