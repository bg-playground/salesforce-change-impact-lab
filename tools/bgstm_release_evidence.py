#!/usr/bin/env python3
"""Build a deterministic BGSTM External Results v1 handoff bundle.

The tool does not call BGSTM. It emits a session creation request and case-result
templates. A future uploader can POST the session, receive its UUID, inject that
session_id into each case template, and submit the cases.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

VALID_SUPPORTING = {"passed", "failed", "not-run"}
OUTCOME_BY_DECISION = {"GO": "passed", "NO-GO": "failed", "REVIEW": "skipped"}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def semantic_cases(pr_impact: dict[str, Any]) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for requirement_id in sorted(pr_impact.get("semantic_evidence", {})):
        evidence = pr_impact["semantic_evidence"][requirement_id]
        decision = evidence.get("release_decision", "REVIEW")
        cases.append(
            {
                "external_id": f"salesforce-change-impact-lab:{requirement_id}:semantic",
                "title": f"{requirement_id} semantic business-intent check",
                "outcome": OUTCOME_BY_DECISION.get(decision, "skipped"),
                "duration_ms": 0,
                "error_message": None if decision == "GO" else _semantic_message(evidence, decision),
                "requirement_external_ids": [requirement_id],
                "auto_register_requirements": False,
                "source": {
                    "kind": "semantic",
                    "decision": decision,
                    "mismatch_count": evidence.get("mismatch_count"),
                },
            }
        )
    return cases


def _semantic_message(evidence: dict[str, Any], decision: str) -> str:
    mismatches = evidence.get("mismatch_count")
    if decision == "NO-GO":
        return f"Business-intent drift detected; mismatches={mismatches}."
    return "Semantic evidence is incomplete or requires review."


def supporting_case(kind: str, status: str) -> dict[str, Any]:
    if status not in VALID_SUPPORTING:
        raise ValueError(f"Unsupported {kind} status: {status}")
    outcome = {"passed": "passed", "failed": "failed", "not-run": "skipped"}[status]
    title = {
        "code-analyzer": "Salesforce Code Analyzer release check",
        "apex-runtime": "Apex/runtime release check",
    }[kind]
    return {
        "external_id": f"salesforce-change-impact-lab:release:{kind}",
        "title": title,
        "outcome": outcome,
        "duration_ms": 0,
        "error_message": None if status == "passed" else (
            f"Required supporting signal failed: {kind}." if status == "failed"
            else f"Required supporting evidence not supplied: {kind}."
        ),
        "requirement_external_ids": [],
        "auto_register_requirements": False,
        "source": {"kind": kind, "status": status},
    }


def release_decision(pr_impact: dict[str, Any], code_analyzer: str, apex_runtime: str) -> tuple[str, str]:
    semantic_decision = pr_impact.get("decision", "REVIEW")
    semantic_cases_map = pr_impact.get("semantic_evidence", {})

    semantic_no_go = sorted(
        req for req, evidence in semantic_cases_map.items()
        if evidence.get("release_decision") == "NO-GO"
    )
    if semantic_decision == "NO-GO" or semantic_no_go:
        ids = ", ".join(semantic_no_go) if semantic_no_go else "PR impact"
        return "NO-GO", f"Business-intent gate rejected: {ids}."

    failed = [name for name, status in (("Code Analyzer", code_analyzer), ("Apex/runtime", apex_runtime)) if status == "failed"]
    if failed:
        return "NO-GO", f"Required supporting signal failed: {', '.join(failed)}."

    missing = [name for name, status in (("Code Analyzer", code_analyzer), ("Apex/runtime", apex_runtime)) if status == "not-run"]
    missing_semantics = pr_impact.get("missing_semantic_evidence", [])
    if semantic_decision == "REVIEW" or missing_semantics or missing:
        details = []
        if missing_semantics:
            details.append("semantic=" + ",".join(sorted(missing_semantics)))
        if missing:
            details.append("supporting=" + ",".join(missing))
        return "REVIEW", "Required evidence incomplete" + (": " + "; ".join(details) if details else ".")

    if semantic_decision in {"GO", "NO-IMPACT"}:
        return "GO", "All required supplied evidence passed."

    return "REVIEW", f"Unrecognized PR impact decision: {semantic_decision}."


def build_bundle(
    pr_impact: dict[str, Any],
    *,
    project_id: str,
    git_sha: str | None,
    git_branch: str | None,
    ci_url: str | None,
    code_analyzer: str,
    apex_runtime: str,
) -> dict[str, Any]:
    decision, reason = release_decision(pr_impact, code_analyzer, apex_runtime)
    cases = semantic_cases(pr_impact)
    cases.extend([
        supporting_case("code-analyzer", code_analyzer),
        supporting_case("apex-runtime", apex_runtime),
    ])

    session_status = "passed" if decision == "GO" else "failed" if decision == "NO-GO" else "aborted"
    case_counts = {
        "total": len(cases),
        "passed": sum(c["outcome"] == "passed" for c in cases),
        "failed": sum(c["outcome"] == "failed" for c in cases),
        "skipped": sum(c["outcome"] == "skipped" for c in cases),
        "flaky": sum(c["outcome"] == "flaky" for c in cases),
    }

    return {
        "schema": "salesforce-change-impact-lab.bgstm-release-evidence.v1",
        "release_decision": decision,
        "release_reason": reason,
        "bgstm_external_results_v1": {
            "session_request": {
                "runner": "salesforce-change-impact-lab@1",
                "project_id": project_id,
                "git_sha": git_sha,
                "git_branch": git_branch,
                "ci_url": ci_url,
                "metadata": {
                    "source": "salesforce-change-impact-lab",
                    "release_decision": decision,
                },
            },
            "case_templates": cases,
            "finish_session_request": {
                "status": session_status,
                "summary": case_counts,
            },
            "upload_sequence": [
                "POST /api/v1/external-results/session with session_request",
                "inject returned session id into each case template as session_id",
                "POST /api/v1/external-results/case for each case",
                "PATCH /api/v1/external-results/session/{session_id} with finish_session_request",
            ],
        },
        "source_summary": {
            "pr_impact_decision": pr_impact.get("decision"),
            "impacted_requirements": sorted(pr_impact.get("semantic_evidence", {}).keys()),
            "code_analyzer": code_analyzer,
            "apex_runtime": apex_runtime,
        },
    }


def render_text(bundle: dict[str, Any]) -> str:
    lines = [
        "BGSTM RELEASE EVIDENCE",
        "",
        f"Decision: {bundle['release_decision']}",
        f"Reason: {bundle['release_reason']}",
        "",
        "Cases:",
    ]
    for case in bundle["bgstm_external_results_v1"]["case_templates"]:
        reqs = ",".join(case["requirement_external_ids"]) or "release-wide"
        lines.append(f"  {case['outcome'].upper():7} {reqs:14} {case['title']}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pr-impact", type=Path, required=True)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--git-sha")
    parser.add_argument("--git-branch")
    parser.add_argument("--ci-url")
    parser.add_argument("--code-analyzer", choices=sorted(VALID_SUPPORTING), required=True)
    parser.add_argument("--apex-runtime", choices=sorted(VALID_SUPPORTING), required=True)
    parser.add_argument("--json-out", type=Path, required=True)
    parser.add_argument("--text-out", type=Path)
    args = parser.parse_args()

    bundle = build_bundle(
        load_json(args.pr_impact),
        project_id=args.project_id,
        git_sha=args.git_sha,
        git_branch=args.git_branch,
        ci_url=args.ci_url,
        code_analyzer=args.code_analyzer,
        apex_runtime=args.apex_runtime,
    )
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(bundle, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.text_out:
        args.text_out.parent.mkdir(parents=True, exist_ok=True)
        args.text_out.write_text(render_text(bundle), encoding="utf-8")

    print(render_text(bundle), end="")
    return 2 if bundle["release_decision"] == "NO-GO" else 0


if __name__ == "__main__":
    raise SystemExit(main())
