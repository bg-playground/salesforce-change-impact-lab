#!/usr/bin/env python3
"""Select same-SHA upstream workflow runs for release-evidence orchestration."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

SCHEMA = "salesforce-change-impact-lab.workflow-evidence-plan.v1"


def load_runs(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    runs = data.get("workflow_runs", [])
    if not isinstance(runs, list):
        raise ValueError("workflow_runs must be a list")
    return runs


def select_run(runs: list[dict[str, Any]], *, expected_sha: str) -> dict[str, Any] | None:
    candidates = [
        run for run in runs
        if run.get("head_sha") == expected_sha and run.get("status") == "completed"
    ]
    if not candidates:
        return None

    def key(run: dict[str, Any]) -> tuple[int, str, int]:
        return (
            int(run.get("run_attempt") or 0),
            str(run.get("updated_at") or run.get("run_started_at") or run.get("created_at") or ""),
            int(run.get("id") or 0),
        )

    selected = max(candidates, key=key)
    return {
        "id": selected.get("id"),
        "name": selected.get("name"),
        "head_sha": selected.get("head_sha"),
        "status": selected.get("status"),
        "conclusion": selected.get("conclusion"),
        "run_attempt": selected.get("run_attempt"),
        "html_url": selected.get("html_url"),
        "created_at": selected.get("created_at"),
        "updated_at": selected.get("updated_at"),
    }


def build_plan(
    *,
    expected_sha: str,
    pr_impact_runs: list[dict[str, Any]],
    code_analyzer_runs: list[dict[str, Any]],
    apex_runtime_runs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    pr_run = select_run(pr_impact_runs, expected_sha=expected_sha)
    code_run = select_run(code_analyzer_runs, expected_sha=expected_sha)
    apex_run = select_run(apex_runtime_runs or [], expected_sha=expected_sha)
    sources = {
        "pr_change_impact": {
            "workflow": "PR Change Impact",
            "artifact": "pr-change-impact-evidence",
            "run": pr_run,
        },
        "salesforce_code_analyzer": {
            "workflow": "Salesforce Code Analyzer",
            "artifact": "salesforce-code-analyzer-release-evidence",
            "run": code_run,
        },
        "salesforce_apex_runtime": {
            "workflow": "Salesforce Apex Runtime",
            "artifact": "salesforce-apex-runtime-evidence",
            "run": apex_run,
        },
    }
    missing = [name for name, source in sources.items() if source["run"] is None]
    return {
        "schema": SCHEMA,
        "git_sha": expected_sha,
        "sources": sources,
        "missing_sources": missing,
    }


def write_github_output(path: Path, plan: dict[str, Any]) -> None:
    mapping = {
        "pr_impact_run_id": plan["sources"]["pr_change_impact"]["run"],
        "code_analyzer_run_id": plan["sources"]["salesforce_code_analyzer"]["run"],
        "apex_runtime_run_id": plan["sources"]["salesforce_apex_runtime"]["run"],
    }
    with path.open("a", encoding="utf-8") as handle:
        for key, run in mapping.items():
            handle.write(f"{key}={run['id'] if run else ''}\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--pr-impact-runs", type=Path, required=True)
    parser.add_argument("--code-analyzer-runs", type=Path, required=True)
    parser.add_argument("--apex-runtime-runs", type=Path)
    parser.add_argument("--json-out", type=Path, required=True)
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args()

    plan = build_plan(
        expected_sha=args.expected_sha,
        pr_impact_runs=load_runs(args.pr_impact_runs),
        code_analyzer_runs=load_runs(args.code_analyzer_runs),
        apex_runtime_runs=load_runs(args.apex_runtime_runs) if args.apex_runtime_runs else [],
    )
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.github_output:
        write_github_output(args.github_output, plan)
    print(json.dumps(plan, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
