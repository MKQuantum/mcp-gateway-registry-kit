# Build It Yourself — Governed MCP on FluxNova

A hands-on workshop. **You write the code.** This guide gives you the
concepts, the contracts between components, and a test suite that tells you
when you're right — but the implementation is yours.

**Time:** 3–4 hours if you're comfortable with Python. Half a day if you're
learning as you go.

**You'll need:** Docker Desktop, a text editor, Python 3.12+ locally
(optional but helpful), and the **OPA CLI**
(https://www.openpolicyagent.org/docs/latest/#running-opa).

**Start from:** `starter-kit.zip` — it contains Dockerfiles, dependency
files, `docker-compose.yml`, the BPMN model, sample inputs, a **test
suite**, and stub source files full of `TODO`s. No solution code.

> **There is an answer key.** `fluxnova-mcp-gateway.zip` is the completed
> version. Use it to unblock yourself after a genuine attempt, not to skip
> ahead — the parts where you're stuck are the parts you're learning.

---

## What you're building, and why

Six services. An AI agent tries to read a ledger (allowed) and then book a
$50M correction (blocked, routed to a human). Every call — allowed or
denied — leaves a linked evidence record.

```
Analyst ─▶ FluxNova BPMN Engine ──(external task)──▶ Worker      [PART 5]
                  ▲                                     │
                  │                                     ▼
            Tasklist approval ◀──(BPMN error)───── Gateway       [PART 3]
                     [PART 4]                          │   ▲
                                              ┌────────┘   └─── OPA  [PART 1]
                                              ▼
                                        MCP Server               [PART 2]
```

**The one idea to hold onto:** the Gateway *verifies* (signatures, tokens,
attestations); the policy engine only *decides* based on claims already
verified. Keeping that line clean is what makes the policy portable across
gateways, languages, and vendors. You'll feel the temptation to blur it in
Part 3 — don't.

---

## Part 0 — Setup (10 min)

```bash
unzip starter-kit.zip && cd starter-kit
opa version     # need 1.x
docker --version
```

Look around. Note what's already there (Dockerfiles, compose, tests) and
what's a stub (every `.py`, plus `policy/gateway_registry_policy.rego`).

---

## Part 1 — The policy (60–90 min)

**Start here.** It needs zero infrastructure, and it has the tightest
feedback loop in the whole stack: edit a file, run one command, know
instantly if you're right.

### The idea

Four guardrails, one versioned Rego module:

| Guardrail | Answers |
|---|---|
| Authorization & identity | Who is this agent, and may it do this? |
| Provenance & attestation | What model/prompt/tools produced this call, and does it chain to the last one? |
| Governance & policy | This file itself — one module, versioned, loaded everywhere |
| Audit & observability | What happened, decided how, with what evidence? |

### Your task

```bash
cd policy
cat gateway_registry_policy_test.rego   # read this first — it's the spec
opa test .                              # FAIL: 5/5 — your starting line
```

Open `gateway_registry_policy.rego`. `identity_verified` is written for you
as a worked example. Everything else is a `TODO` with a hint.

Work top to bottom, running `opa test .` after each rule. Green is the goal:

```
PASS: 5/5
```

### Things that will bite you

- **Rego rules with the same name are OR'd.** `delegation_valid` is two
  rules: one for reads, one for writes-with-a-delegator. That's idiomatic,
  not a mistake.
- **A missing key isn't false, it's undefined.** For "fresh session, no
  prior attestation", you need `not data.registry.last_attestation_hash[...]`
  as its own rule rather than comparing to `""`.
- **Order matters in the decision chain.** Safety hold must beat everything,
  including a perfectly valid in-scope read. Test 5 checks exactly this.
- **`some x in y` needs `import rego.v1`** on older OPA. On 1.x it's default.

### Checkpoint

```bash
opa test .        # PASS: 5/5
opa check gateway_registry_policy.rego
opa eval -i ../examples/write-no-approval.json \
  -d gateway_registry_policy.rego -d gateway_registry_data.json \
  'data.mcp.gateway.authz.decision' --format pretty
```

Expected:

```json
{
  "allow": false,
  "reason": "step_up_required",
  "obligations": ["require_human_approval", "route_to_fluxnova_user_task"]
}
```

Run the other two examples too. `read-allowed.json` →
`granted_within_scope`. `write-after-approval.json` → also
`granted_within_scope`, because the human attested.

**You've just built the thing that makes the rest meaningful.** Everything
else is plumbing that calls this.

---

## Part 2 — The MCP server (30 min)

### The idea

This stands in for a real ERP or trade-execution MCP server. Two tools, one
safe and one dangerous, so the policy has something meaningful to reason
about.

### Your task

Open `mock-mcp-server/server.py`. Build:

- `erp.query(business_key)` → `book_value`, `confirmed_value`, `variance`
- `trade.correct(business_key, amount)` → confirms and returns the new balance

Seed `TRD-2026-04471` with a deliberate mismatch so there's a variance worth
escalating.

Use the official SDK (`from mcp.server.fastmcp import FastMCP`) and serve
over **Streamable HTTP** — the Gateway reaches it over the network, so stdio
won't do.

### Checkpoint

```bash
cd mock-mcp-server
pip install -r requirements.txt
python server.py          # should bind port 9000
```

In another terminal, confirm it's listening:

```bash
curl -s -o /dev/null -w "%{http_code}\n" localhost:9000/mcp
```

Anything other than a connection error means it's up. (A bare `curl` won't
speak MCP properly — that's fine, you're only proving the port is live.)

---

## Part 3 — The Gateway (90 min) ⭐ the hard part

### The idea

Every call goes through here. It's a **Policy Enforcement Point**: it
verifies who's calling, asks OPA what to do, and either proxies the call or
refuses it.

The six steps, in order:

1. Verify the bearer JWT → get the agent's identity
2. Build the AgBOM (model, prompt hash, tool manifest, chain link)
3. POST to OPA, get `{allow, reason, obligations}`
4. **Emit an audit event — always, allow or deny**
5. Denied → return the decision, don't touch the MCP server
6. Allowed → call the tool, save a new chain hash, return the result

### Your task

Open `gateway/app.py` and fill in the `TODO`s. The stub has the imports,
config, and function signatures; you write the bodies.

### Where people get this wrong

**Blurring verify and decide.** It's tempting to have Rego check the JWT
signature. Don't. Rego consumes `identity_token.verified == true` — a claim
*you* produced in `verify_identity()`. That separation is why the same
policy file can sit behind a Python gateway, a Go gateway, or a vendor
product.

**Logging only the allows.** Emit the audit event *before* you return on a
deny. An evidence trail with the refusals missing is exactly the thing
regulators ask about.

**Calling the MCP server before checking the decision.** Obvious when
written down; surprisingly easy to do while refactoring.

**Forgetting the chain.** After a successful call, PUT the new hash into
OPA's data store, or the next call's `attestation_chained` check has nothing
to compare against and you'll get confusing denials.

### Checkpoint

```bash
cd gateway && pip install -r requirements.txt
uvicorn app:app --port 8000 &
curl localhost:8000/healthz                      # {"status":"ok"}
curl -X POST localhost:8000/v1/invoke -d '{}'    # should reject (401 or 422)
```

For a full local test you'll need OPA running:

```bash
opa run --server --addr localhost:8181 \
  ../policy/gateway_registry_policy.rego ../policy/gateway_registry_data.json &
```

Then POST a real body to `/v1/invoke` with a JWT you mint yourself and
confirm you get `step_up_required` for a `trade.correct`.

---

## Part 4 — The BPMN process (30 min)

### The idea

This is the part most agent frameworks don't have: a **durable, modelled**
place for "waiting on a human" to live. If the worker crashes mid-approval,
the process instance doesn't care.

### Your task

`bpmn/trade-reconciliation.bpmn` is provided — hand-writing BPMN XML is
miserable and teaches you nothing. **But open it in the FluxNova Modeler**
(https://github.com/finos/fluxnova-modeler) and trace the flow:

```
Start ─▶ [Query ERP Balances] ─▶ [Initiate Correction] ─▶ End
              external task          external task  │
                                                    │ boundary error
                                                    ▼  STEP_UP_REQUIRED
                                          [Trader approval required]
                                            user task, group "traders"
                                                    │
                                                    └──▶ back to Initiate Correction
```

Understand three things before moving on:

1. **Service tasks are `camunda:type="external"`** with a `topic`. That's
   what your worker subscribes to. The engine doesn't run your code — it
   parks the task and waits.
2. **The boundary error event** catches `STEP_UP_REQUIRED`. That's the hook
   your worker triggers when policy says step-up.
3. **The loop back** means approval doesn't restart anything; the same
   instance retries the same task with `humanAttestation=true`.

**Optional exercise:** add a second boundary event — a 4-hour timer that
escalates unapproved corrections to a supervisor.

---

## Part 5 — The worker (60 min)

### The idea

The bridge. It polls FluxNova for parked tasks, calls the Gateway, and
pushes the outcome back into the process.

### Your task

Open `worker/worker.py`. Build the poll loop and the three outcome paths:

| Gateway says | You call | Result |
|---|---|---|
| allowed | `POST .../complete` | process moves on |
| `route_to_fluxnova_user_task` | `POST .../bpmnError` code `STEP_UP_REQUIRED` | boundary event fires, Tasklist task appears |
| any other deny | `POST .../failure` | shows as an incident in Control Center |

### The part that actually matters

Read `startUserId` and `businessKey` **from the task's variables**, not from
config. That's the non-repudiation chain: the policy requires a named
`human_delegator` for any write, and that name comes from whoever started
the process instance. Hard-code it and you've built a demo; read it from the
instance and you've built an audit trail.

### Gotchas

- FluxNova wraps variables as `{"value": ..., "type": ...}` — unwrap them.
- `asyncResponseTimeout` makes `fetchAndLock` a *long poll*. Don't add a
  sleep on top; you'll just add latency.
- Wrap the loop body in try/except. FluxNova takes a minute to boot and the
  worker shouldn't die in the meantime.
- A step-up is **not** a failure. Using `failure` instead of `bpmnError`
  creates an incident instead of a Tasklist entry, and the human never sees
  it.

### Checkpoint

Worker starts, connects, and logs one line per task with the decision.

---

## Part 6 — Run it all (20 min)

```bash
docker compose up --build
```

Wait for http://localhost:8080 to load (1–2 min first boot). Then:

```bash
# Deploy the process model
curl -u demo:demo -X POST http://localhost:8080/engine-rest/deployment/create \
  -F "deployment-name=trade-reconciliation" \
  -F "trade-reconciliation.bpmn=@bpmn/trade-reconciliation.bpmn"

# Start an instance
curl -u demo:demo -X POST \
  http://localhost:8080/engine-rest/process-definition/key/trade-reconciliation/start \
  -H 'Content-Type: application/json' \
  -d '{"businessKey":"TRD-2026-04471","variables":{
        "businessKey":{"value":"TRD-2026-04471","type":"String"},
        "startUserId":{"value":"trader.jsmith@bank.example","type":"String"},
        "correctionAmount":{"value":50000000,"type":"Long"},
        "humanAttestation":{"value":false,"type":"Boolean"}}}'

# Watch the decisions
docker compose logs gateway | grep audit_event
```

### Success looks like

```
"tool": "erp.query",     "decision": true,  "reason": "granted_within_scope"
"tool": "trade.correct", "decision": false, "reason": "step_up_required"
```

Then approve it: http://localhost:8080 → log in `demo`/`demo` → **Tasklist**
→ claim *"Trader approval required"* → tick the box → Complete.

Check the logs again. A third decision appears: the same `trade.correct`,
now `"decision": true`.

**That's the whole pattern working.** A dangerous action was stopped,
queued for a human, approved, and executed — with an unbroken evidence trail.

---

## Part 7 — Prove it to yourself

Don't skip these. Each one teaches something the happy path doesn't.

**1. Break the policy on purpose.** In `gateway_registry_data.json`, add
your agent to `safety_hold_agents`. Restart OPA
(`docker compose restart opa`) and run the demo. Everything denies —
including the harmless read. That's the rule hierarchy: safety beats
everything.

**2. Try to bypass the Gateway.** Point `MCP_SERVER_URL` in the worker
straight at the MCP server, skipping the Gateway entirely. It works — no
policy, no audit trail. **That's the lesson:** the Gateway is only a control
if the network stops you going around it. See the `NetworkPolicy` in the
Kubernetes README for the real fix.

**3. Break the chain.** Manually PUT a wrong hash into OPA's registry and
watch calls start failing `provenance_incomplete_or_unchained`. Tampering is
detectable.

**4. Check the evidence.** In Control Center, find your instance and read
the history. One timeline — read, block, approval, retry — all joined by
`process_instance_id`. Compare that to reconstructing the same story from
three separate log systems.

---

## Where to go next

Roughly in order of value:

1. **Real identity.** Replace `verify_identity()` with SPIFFE/SPIRE SVIDs or
   mTLS client certs. Deliberately isolated so this is a one-function change.
2. **Real AgBOM.** Wire it to your actual model version, system prompt
   digest, and tool manifest, and emit SPDX 3.1 AI Profile documents. *Be
   precise about the claim:* an SBOM is component provenance — one input to
   an evidence chain, not proof that a given invocation was legitimate.
3. **Persist the audit events.** Stdout is fine for a demo. Append-only
   storage with verified hash links is the real thing.
4. **OPA as a sidecar.** Sub-millisecond decisions, and a policy-engine
   outage can't take enforcement down from across the cluster. Decide your
   fail-closed behaviour explicitly while you're in there.
5. **Policy bundles.** Signed, versioned bundles from object storage instead
   of a ConfigMap — which is also what makes `policy_version` a real audit
   artifact.

---

## If you're stuck

1. **Re-read the test/checkpoint.** It usually states the expectation more
   precisely than the prose.
2. **Shrink the problem.** `opa eval` a single rule. `curl` a single
   endpoint. Don't debug six services at once.
3. **Check the logs of one service:** `docker compose logs gateway`
4. **Then** open the answer key — and diff it against yours rather than
   copying. The difference is the lesson.

---

## Reference

- FluxNova: https://github.com/finos/fluxnova-bpm-platform · https://docs.fluxnova.finos.org/
- Sandbox, no install: https://demo.fluxnova.finos.org/
- Rego language: https://www.openpolicyagent.org/docs/latest/policy-language/
- MCP Python SDK: https://github.com/modelcontextprotocol/python-sdk
- Camunda 7 External Task API (FluxNova shares this lineage):
  https://docs.camunda.org/manual/7.20/reference/rest/external-task/
