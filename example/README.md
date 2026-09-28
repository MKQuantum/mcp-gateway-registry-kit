# example/ — run the whole stack

## Docker Compose (simplest)

```bash
docker compose up --build
```

Wait for http://localhost:8080 to load (1–2 min first boot), then:

```bash
bash run-demo.sh
```

Watch the decisions: `docker compose logs gateway | grep audit_event`.

Approve the blocked write: open http://localhost:8080, log in `demo`/`demo`,
go to **Tasklist**, claim *"Trader approval required"*, tick the approval
box, Complete. Run the log command again — a third decision appears, now
allowed.

## Kubernetes

```bash
./deploy.sh
```

See [`../docs/kubernetes.md`](../docs/kubernetes.md) for moving off `kind`
onto a real cluster, and why the included `NetworkPolicy` matters.

## What's here

- `docker-compose.yml` — six services, builds from `../src/`
- `deploy.sh` / `run-demo.sh` — Kubernetes path
- `k8s/all-in-one.yaml` — all manifests
- `sample-inputs/` — three JSON files you can feed straight to `opa eval`
  to see the three decisions without standing up anything
