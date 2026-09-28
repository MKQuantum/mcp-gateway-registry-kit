# FAQ

**Why Python for the worker when FluxNova ships a Java client?**
External tasks are a REST contract (`fetchAndLock` / `complete` /
`bpmnError`), not a Java-only feature. Python keeps the whole agent side of
the stack in one language.

**Why not call the MCP server directly from the worker?**
Then the Gateway is advice, not a control. See `docs/kubernetes.md` for the
NetworkPolicy that turns it into an enforced boundary.

**Does the Rego policy verify signatures?**
No, and it's not supposed to. See `docs/policy-guide.md` — the Gateway
verifies; the policy only decides based on what's already verified.

**FluxNova 3.0 added native MCP plugin support — should I use that instead?**
Maybe, if you're starting fresh on 3.0+. This kit uses the external-task
pattern because it works on any FluxNova version and keeps the Gateway
independently deployable. See `docs/architecture.md`.

**Where's the real SPDX/AgBOM generation?**
Stubbed in `build_agbom()` in the Gateway — it hashes static strings so the
chaining logic has something to chain. Wiring it to a real model version,
prompt digest, and SPDX 3.1 AI Profile document is the top item in
"Where to go next" in `workshop/BUILD-IT-YOURSELF.md`.
