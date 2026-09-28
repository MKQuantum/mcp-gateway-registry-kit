# Security Policy

## Reporting a vulnerability

Please **do not** open a public issue for security vulnerabilities.

Instead, use GitHub's private vulnerability reporting: go to the **Security**
tab of this repository → **Report a vulnerability**. If that's not available,
email the maintainers listed in `CODEOWNERS`.

Include:
- What you found and where (file / endpoint / policy rule)
- Reproduction steps or a proof of concept
- What you'd expect the correct (safe) behavior to be

## Scope

This is a reference implementation for a governance *pattern*, not a hardened
product. In particular, know before you deploy this anywhere real:

- The JWT identity check in `src/gateway/app.py` uses a shared HMAC secret
  for demo simplicity. Production deployments should use SPIFFE/SPIRE or
  mTLS — see `docs/architecture.md`.
- Default credentials (`demo`/`demo`, database passwords) throughout
  `example/` are for local demos only. Rotate everything before any shared
  or internet-facing deployment.
- The NetworkPolicy in `example/k8s/all-in-one.yaml` only takes effect on a
  CNI that enforces it (Calico, Cilium) — not on kind's default CNI.

We'll still take reports on the reference implementation itself (e.g., a
policy bypass that shouldn't exist even in a demo).
