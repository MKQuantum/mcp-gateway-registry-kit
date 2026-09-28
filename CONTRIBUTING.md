# Contributing

Thanks for considering a contribution.

## Ways to contribute
- **Policy improvements** — new guardrail rules, tighter checks, more test cases in `src/policy/`
- **New MCP server integrations** — swap the mock server for a real one and document it
- **Alternate identity backends** — SPIFFE/SPIRE, mTLS — replacing `verify_identity()` in `src/gateway/app.py`
- **Docs and workshop fixes** — typos, unclear steps, missing checkpoints in `workshop/`

## Before you open a PR
1. `cd src/policy && opa fmt --diff *.rego && opa test .` — must pass 5/5
2. Validate any YAML you touched: `python -c "import yaml; yaml.safe_load(open('FILE'))"`
3. If you touched the BPMN model, open it in FluxNova Modeler and confirm it still deploys
4. Update `workshop/` if your change affects the build-it-yourself flow — the stub and the
   answer key (`src/`) should never drift apart

## Pull requests
- One logical change per PR
- Describe what changed and why in the description, not just the commit list
- CI (`.github/workflows/ci.yml`) must be green before review

## Reporting issues
Use the issue templates under `.github/ISSUE_TEMPLATE/`. For policy bugs, include the
`opa eval` input and the decision you got vs. the decision you expected — that's usually
enough to reproduce.

## Code of conduct
This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md).
