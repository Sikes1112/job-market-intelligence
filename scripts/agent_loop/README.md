# Codex Layer Implementation Loop

## What this does

This controller runs Layer 34C as a bounded loop:

1. select the next incomplete roadmap step
2. invoke a fresh Codex implementation run
3. validate structured output
4. repeat through the roadmap
5. run deterministic full verification
6. invoke a fresh read-only adversarial audit
7. run bounded remediation when required
8. reverify and reaudit
9. stop at COMPLETE_PENDING_COMMIT after PASS

The controller deliberately does not auto-commit by default.

## Requirements

- run from the repository root
- Codex CLI installed and authenticated
- Python 3.11+
- backend and frontend dependencies installed
- `codex exec` available
- repository commands in `verification.py` valid for this repo

## Optional Codex configuration

Use your existing Codex configuration:

```bash
export CODEX_PROFILE=xhigh
```

Or set a model override supported by your installation:

```bash
export CODEX_MODEL="<your configured model identifier>"
```

The controller does not guess a model identifier.

## Bootstrap

From the repository root:

```bash
bash /path/to/bootstrap_layer_34c_loop.sh .
```

## Inspect generated files

```bash
find docs/implementation/layer_34c scripts/agent_loop -type f | sort
```

## Start the loop

```bash
python3 scripts/agent_loop/run_layer_loop.py --repo . --mode run
```

## Inspect status

```bash
python3 scripts/agent_loop/run_layer_loop.py --repo . --mode status
```

## Run deterministic verification only

```bash
python3 scripts/agent_loop/run_layer_loop.py --repo . --mode verify
```

## Run verification plus a fresh audit

```bash
python3 scripts/agent_loop/run_layer_loop.py --repo . --mode audit
```

## Runtime artifacts

Generated reports are written under:

```text
.agent_loop/layer_34c/
```

Add this runtime directory to `.gitignore` unless you intentionally want to commit selected audit artifacts.

## Important safety behavior

- implementation and remediation use `workspace-write`
- audit uses `read-only`
- no dangerous sandbox bypass is used
- no automatic push or pull request exists
- no automatic commit occurs
- maximum remediation cycles are bounded
- state advances only from structured results and deterministic checks

## Before the first run

Review:

- Layer 34C specification
- roadmap acceptance criteria
- verification commands
- current git status
- Codex profile/model configuration

The loop is autonomous within the approved specification, not autonomous product management.
