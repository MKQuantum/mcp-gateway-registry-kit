#!/usr/bin/env bash
# Deploy the whole Gateway Registry stack onto a local kind cluster.
# Usage:  ./deploy.sh
set -Eeuo pipefail

CLUSTER=${CLUSTER:-mcp-gov}
NS=mcp-gov

echo "==> 1/6  Creating kind cluster (if it doesn't exist)"
if ! kind get clusters 2>/dev/null | grep -qx "$CLUSTER"; then
  kind create cluster --name "$CLUSTER"
else
  echo "    cluster '$CLUSTER' already exists, reusing"
fi

echo "==> 2/6  Building images"
docker build -t mcp-gov/gateway:0.1.0   ../src/gateway
docker build -t mcp-gov/worker:0.1.0    ../src/worker
docker build -t mcp-gov/mock-mcp:0.1.0  ../src/mock-mcp-server

echo "==> 3/6  Loading images into kind"
kind load docker-image mcp-gov/gateway:0.1.0  --name "$CLUSTER"
kind load docker-image mcp-gov/worker:0.1.0   --name "$CLUSTER"
kind load docker-image mcp-gov/mock-mcp:0.1.0 --name "$CLUSTER"

echo "==> 4/6  Creating namespace + policy ConfigMap"
kubectl apply -f - <<EOF
apiVersion: v1
kind: Namespace
metadata:
  name: ${NS}
EOF
kubectl create configmap gateway-policy \
  --from-file=../src/policy/gateway_registry_policy.rego \
  --from-file=../src/policy/gateway_registry_data.json \
  -n "$NS" --dry-run=client -o yaml | kubectl apply -f -

echo "==> 5/6  Applying manifests"
kubectl apply -f k8s/all-in-one.yaml

echo "==> 6/6  Waiting for pods (FluxNova takes ~1-2 min on first boot)"
kubectl -n "$NS" rollout status deploy/postgres  --timeout=180s
kubectl -n "$NS" rollout status deploy/opa       --timeout=120s
kubectl -n "$NS" rollout status deploy/mock-mcp  --timeout=120s
kubectl -n "$NS" rollout status deploy/gateway   --timeout=120s
kubectl -n "$NS" rollout status deploy/fluxnova  --timeout=420s
kubectl -n "$NS" rollout status deploy/worker    --timeout=120s

cat <<'DONE'

============================================================
  Stack is up.

  Port-forward the pieces you want to poke at:

    kubectl -n mcp-gov port-forward svc/fluxnova 8080:8080 &
    kubectl -n mcp-gov port-forward svc/opa      8181:8181 &
    kubectl -n mcp-gov port-forward svc/gateway  8000:8000 &

  Then:
    FluxNova web apps : http://localhost:8080/
    OPA health        : curl localhost:8181/health
    Gateway health    : curl localhost:8000/healthz

  Next: deploy the BPMN model and run the demo (see README Step 7).
============================================================
DONE
