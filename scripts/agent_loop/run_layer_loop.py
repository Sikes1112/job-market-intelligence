from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from codex_runner import CodexRunError, run_codex  # noqa: E402
from git_guard import current_head, diff_check, ensure_repository, status_short  # noqa: E402
from schemas import LoopPaths, load_json, write_json  # noqa: E402
from state import append_artifact, load_state, next_step, save_state  # noqa: E402
from verification import default_full_verification, results_to_json  # noqa: E402


class LoopError(RuntimeError):
    pass


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def timestamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def implementation_prompt(paths: LoopPaths, step: str) -> str:
    base = read_text(paths.layer_dir / "LAYER_34C_IMPLEMENTATION_PROMPT.md")
    return (
        f"{base}\n\n"
        f"## Controller Runtime Instruction\n\n"
        f"Current roadmap step: {step}\n"
        f"Implement only {step}. Read its exact section in "
        f"LAYER_34C_ROADMAP.md.\n"
    )


def audit_prompt(paths: LoopPaths, verification_path: Path) -> str:
    base = read_text(paths.layer_dir / "LAYER_34C_AUDIT_PROMPT.md")
    return (
        f"{base}\n\n"
        f"## Controller Runtime Instruction\n\n"
        f"Verification evidence: {verification_path.relative_to(paths.repo_root)}\n"
        f"Inspect the actual repository and do not rely on implementation summaries.\n"
    )


def remediation_prompt(paths: LoopPaths, audit_path: Path) -> str:
    base = read_text(paths.layer_dir / "LAYER_34C_REMEDIATION_PROMPT.md")
    return (
        f"{base}\n\n"
        f"## Controller Runtime Instruction\n\n"
        f"Audit report: {audit_path.relative_to(paths.repo_root)}\n"
    )


def run_implementation(paths: LoopPaths, state: dict, contract: dict, step: str) -> None:
    state["status"] = "IMPLEMENTING_STEP"
    state["current_step"] = step
    save_state(paths.layer_dir / "LAYER_34C_STATE.json", state)

    output = paths.run_dir / f"{timestamp()}_{step.replace('.', '_')}_implementation.json"
    run_codex(
        repo_root=paths.repo_root,
        sandbox="workspace-write",
        schema_path=paths.schema_dir / "implementation_result.schema.json",
        output_path=output,
        prompt=implementation_prompt(paths, step),
    )
    result = load_json(output)
    append_artifact(state, "implementation_reports", output.relative_to(paths.repo_root))

    if result["decision"] != "STEP_COMPLETE":
        blocking_issues = result.get("blocking_issues", [])

        if result["decision"] == "STEP_BLOCKED" and not blocking_issues:
            retry_output = paths.run_dir / (
                f"{timestamp()}_{step.replace('.', '_')}_implementation_retry.json"
            )
            retry_prompt = (
                implementation_prompt(paths, step)
                + "\n\n## Mandatory Retry Instruction\n\n"
                + "The prior run returned STEP_BLOCKED without identifying any "
                  "blocking issue. That is not a valid block. Continue through "
                  "implementation, testing, and verification. Return STEP_BLOCKED "
                  "only if you identify and list a concrete blocking issue."
            )

            run_codex(
                repo_root=paths.repo_root,
                sandbox="workspace-write",
                schema_path=paths.schema_dir / "implementation_result.schema.json",
                output_path=retry_output,
                prompt=retry_prompt,
            )

            append_artifact(
                state,
                "implementation_reports",
                retry_output.relative_to(paths.repo_root),
            )
            result = load_json(retry_output)
            blocking_issues = result.get("blocking_issues", [])

        if result["decision"] != "STEP_COMPLETE":
            state["status"] = "HUMAN_ESCALATION"
            save_state(paths.layer_dir / "LAYER_34C_STATE.json", state)
            detail = "; ".join(blocking_issues) or "No concrete blocking issue supplied"
            raise LoopError(f"Implementation step {step} blocked: {detail}")

    state["status"] = "VERIFYING_STEP"
    save_state(paths.layer_dir / "LAYER_34C_STATE.json", state)
    diff_check(paths.repo_root)

    completed = state.setdefault("completed_steps", [])
    if step not in completed:
        completed.append(step)
    state["status"] = "STEP_COMPLETE"
    state["current_step"] = None
    save_state(paths.layer_dir / "LAYER_34C_STATE.json", state)


def run_full_verification(paths: LoopPaths, state: dict) -> Path:
    results = default_full_verification(paths.repo_root)
    output = paths.run_dir / f"{timestamp()}_verification.json"
    payload = results_to_json(results)
    write_json(output, payload)
    append_artifact(state, "verification_reports", output.relative_to(paths.repo_root))
    save_state(paths.layer_dir / "LAYER_34C_STATE.json", state)
    if not payload["passed"]:
        raise LoopError(f"Full verification failed; inspect {output}")
    return output


def run_audit(paths: LoopPaths, state: dict, verification_path: Path) -> Path:
    state["status"] = "AUDITING"
    save_state(paths.layer_dir / "LAYER_34C_STATE.json", state)

    output = paths.run_dir / f"{timestamp()}_audit.json"
    run_codex(
        repo_root=paths.repo_root,
        sandbox="read-only",
        schema_path=paths.schema_dir / "audit_result.schema.json",
        output_path=output,
        prompt=audit_prompt(paths, verification_path),
    )
    append_artifact(state, "audit_reports", output.relative_to(paths.repo_root))
    result = load_json(output)
    decision = result["decision"]
    state["last_audit_decision"] = decision

    if decision == "PASS":
        state["status"] = "PASS"
    elif decision == "REMEDIATION_REQUIRED":
        state["status"] = "REMEDIATION_REQUIRED"
    else:
        state["status"] = "HUMAN_ESCALATION"

    save_state(paths.layer_dir / "LAYER_34C_STATE.json", state)
    return output


def run_remediation(
    paths: LoopPaths,
    state: dict,
    contract: dict,
    audit_path: Path,
) -> None:
    maximum = int(contract["maximum_remediation_cycles"])
    cycle = int(state.get("remediation_cycle", 0)) + 1
    if cycle > maximum:
        state["status"] = "HUMAN_ESCALATION"
        save_state(paths.layer_dir / "LAYER_34C_STATE.json", state)
        raise LoopError("Maximum remediation cycles exceeded")

    state["remediation_cycle"] = cycle
    state["status"] = "REMEDIATING"
    save_state(paths.layer_dir / "LAYER_34C_STATE.json", state)

    output = paths.run_dir / f"{timestamp()}_remediation_{cycle}.json"
    run_codex(
        repo_root=paths.repo_root,
        sandbox="workspace-write",
        schema_path=paths.schema_dir / "remediation_result.schema.json",
        output_path=output,
        prompt=remediation_prompt(paths, audit_path),
    )
    append_artifact(state, "remediation_reports", output.relative_to(paths.repo_root))
    result = load_json(output)
    if result["decision"] != "REMEDIATION_COMPLETE":
        state["status"] = "HUMAN_ESCALATION"
        save_state(paths.layer_dir / "LAYER_34C_STATE.json", state)
        raise LoopError("Remediation blocked")

    state["status"] = "REVERIFYING"
    save_state(paths.layer_dir / "LAYER_34C_STATE.json", state)


def write_handoff(paths: LoopPaths, state: dict) -> None:
    handoff = paths.repo_root / "docs" / "roadmap" / "LAYER_35_HANDOFF.md"
    handoff.parent.mkdir(parents=True, exist_ok=True)
    handoff.write_text(
        "# Layer 35 Handoff\n\n"
        "Layer 34C passed implementation, deterministic verification, "
        "and an independent adversarial audit.\n\n"
        "This file is a handoff only. It does not define Layer 35.\n\n"
        "## Durable predecessor\n\n"
        f"- Starting commit: {state.get('starting_commit')}\n"
        f"- Current working commit: {current_head(paths.repo_root)}\n"
        f"- Audit decision: {state.get('last_audit_decision')}\n"
        f"- Remediation cycles: {state.get('remediation_cycle', 0)}\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    parser.add_argument(
        "--mode",
        choices=["run", "status", "verify", "audit"],
        default="run",
    )
    args = parser.parse_args()

    paths = LoopPaths.build(Path(args.repo))
    paths.run_dir.mkdir(parents=True, exist_ok=True)
    ensure_repository(paths.repo_root)

    contract = load_json(paths.layer_dir / "LAYER_34C_COMPLETION_CONTRACT.json")
    state_path = paths.layer_dir / "LAYER_34C_STATE.json"
    state = load_state(state_path)

    if not state.get("starting_commit"):
        state["starting_commit"] = current_head(paths.repo_root)
        save_state(state_path, state)

    if args.mode == "status":
        print(json.dumps(state, indent=2))
        print(status_short(paths.repo_root), end="")
        return 0

    if args.mode == "verify":
        verification = run_full_verification(paths, state)
        print(verification)
        return 0

    if args.mode == "audit":
        verification = run_full_verification(paths, state)
        audit = run_audit(paths, state, verification)
        print(audit)
        return 0

    while True:
        step = next_step(contract, state)
        if step is not None:
            run_implementation(paths, state, contract, step)
            continue

        state["status"] = "IMPLEMENTATION_COMPLETE"
        save_state(state_path, state)
        verification = run_full_verification(paths, state)
        audit_path = run_audit(paths, state, verification)
        audit_result = load_json(audit_path)

        if audit_result["decision"] == "PASS":
            state["status"] = "COMPLETE_PENDING_COMMIT"
            save_state(state_path, state)
            write_handoff(paths, state)
            print(
                "Layer 34C passed. State is COMPLETE_PENDING_COMMIT. "
                "Run the repository durability/commit workflow next."
            )
            return 0

        if audit_result["decision"] == "HUMAN_ESCALATION":
            raise LoopError(f"Audit requires human escalation: {audit_path}")

        run_remediation(paths, state, contract, audit_path)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (LoopError, CodexRunError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1) from error
