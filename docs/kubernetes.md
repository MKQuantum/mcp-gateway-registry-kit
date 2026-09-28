# Running on Kubernetes

`example/k8s/all-in-one.yaml` deploys all six services: Postgres, FluxNova,
OPA, the mock MCP server, the Gateway, and the worker.

```bash
cd example
./deploy.sh          # creates a kind cluster, builds images, applies manifests
```

## Moving off kind

**Images** — push to a registry your cluster can pull from and update the
`image:` fields; drop the `kind load` step.

**Storage** — the Postgres `emptyDir` is demo-only. Use a PVC or a managed
database, and point FluxNova at it via `DB_URL` / `DB_USERNAME` /
`DB_PASSWORD` (these env var names come straight from FluxNova's own
`docker-script.sh`).

**NetworkPolicy** — the manifest restricts the mock MCP server to ingress
from the Gateway pod only. This is what makes the Gateway an actual
enforcement boundary rather than a convention. It requires a CNI that
enforces NetworkPolicy (Calico, Cilium) — kind's default CNI ignores it
silently. Verify with:

```bash
kubectl -n mcp-gov exec deploy/worker -- \
  python -c "import httpx; print(httpx.get('http://mock-mcp:9000/mcp', timeout=5).status_code)"
```

That should fail on an enforcing CNI and succeed on kind.
