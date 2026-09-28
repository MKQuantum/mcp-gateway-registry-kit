# MCP Gateway Registry Kit

A reference implementation of the **Gateway Registry pattern** — identity,
policy-as-code, provenance, and audit for Model Context Protocol deployments
in regulated environments — running on [FluxNova](https://github.com/finos/fluxnova-bpm-platform),
the FINOS BPMN engine.

From the talk *Beyond the Prototype: Production Guardrails for MCP in
Regulated Finance* (MCP Dev Summit Toronto, October 2026).

---

## The problem

MCP standardizes *how* an agent talks to a tool. It says nothing about
*who's allowed to*, *what evidence gets produced*, or *what happens when the
answer is "not without a human."* In regulated finance, that gap is the
whole ballgame: SOX requires certified controls, GDPR requires traceability,
and the SEC gives you four days to explain what happened. "We have logs"
isn't an answer to any of those.

This kit closes that gap with four guardrails — authorization & identity,
provenance & attestation, governance & policy, audit & observability —
expressed as one portable, testable Rego policy, enforced at a gateway that
sits between every agent and every MCP server.

## The pattern

<p align="center"><<img width="1282" height="605" alt="image" src="https://github.com/user-attachments/assets/b39e1e2e-9a1b-4418-8650-8e3d1e7b871a" /p>

- **Registry** (control plane) — what's known: server catalog, capabilities,
  policy rules, SBOM/SPDX metadata, approval status
- **Gateway** (enforcement plane) — what's enforced: identity verification,
  RBAC, the OPA policy decision, tool filtering, audit generation

Full write-up: [`docs/architecture.md`](docs/architecture.md).

## What's in this repository

Same shape as most infra resource kits: a working reference implementation
you can run today, and the individual pieces documented well enough to
replace with your own.

| Folder | What it is |
|---|---|
| [`src/`](src/) | The complete, working implementation — policy, Gateway, worker, mock MCP server, BPMN model |
| [`example/`](example/) | Run the whole stack with one command (Docker Compose or Kubernetes) |
| [`workshop/`](workshop/) | **Build it yourself.** Same components as stubs with a test suite — you write the code, we tell you when it's right |
| [`docs/`](docs/) | Architecture, policy guide, the [8-phase Gateway Playbook mapped to this kit](docs/playbook.md), Kubernetes notes, FAQ |
| [`slides/`](slides/) | Key diagrams from the MCP Dev Summit talk this kit accompanies |

## Quick start

```bash
git clone <this-repo> && cd mcp-gateway-registry-kit/example
docker compose up --build
# wait for http://localhost:8080, then:
bash run-demo.sh
```

Want to learn it by building it? Start with
[`workshop/BUILD-IT-YOURSELF.md`](workshop/BUILD-IT-YOURSELF.md).

## The policy

Everything above is downstream of one file:
[`src/policy/gateway_registry_policy.rego`](src/policy/gateway_registry_policy.rego) —
`opa check` clean, 5/5 `opa test` passing, one rule hierarchy: safety beats
security beats contractual beats organizational.

```bash
cd src/policy && opa test . -v
```

See [`docs/policy-guide.md`](docs/policy-guide.md) for what each guardrail rule
does and why.

## Standards and Regulatory Alignment

By leveraging this pattern and policy, several standards and global regulation control requirements will be addressed.

See the following risk and controls matrix to understand how risk domains are mapped to the guardrails as well as to the global standards, frameworks, and regulations: [`docs/Agentic_Mesh_Risk_and_Controls_Framework.xlsx`](docs/Agentic_Mesh_Risk_and_Controls_Framework.xlsx)

## Status

This is a reference implementation of a *pattern*, not a hardened product.
See [`SECURITY.md`](SECURITY.md) for what to change before any real deployment
— identity verification in particular is a JWT stand-in for SPIFFE/SPIRE or
mTLS.

## License

[Apache License 2.0](LICENSE) — the same license FluxNova and OPA use.

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md). Issues and PRs welcome — this is
meant to be adapted, not just read.
