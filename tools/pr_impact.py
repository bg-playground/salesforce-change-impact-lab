#!/usr/bin/env python3
"""Deterministic PR-aware Salesforce business-impact selector."""
from __future__ import annotations
import argparse
import importlib.util
import json
import sys
from pathlib import Path

SEMANTIC_KINDS = ("validation-rule", "flow", "permission-set")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_changed_file(path: Path) -> list[str]:
    """Load one repository-relative changed path per line."""
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _load_tool(filename: str, module_name: str):
    tool = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(module_name, tool)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def run_semantic(metadata: Path, contract: Path, kind: str = "validation-rule") -> dict:
    if kind == "validation-rule":
        module = _load_tool("impact_lab.py", "impact_lab_for_pr")
    elif kind == "flow":
        module = _load_tool("flow_impact.py", "flow_impact_for_pr")
    elif kind == "permission-set":
        module = _load_tool("permission_impact.py", "permission_impact_for_pr")
    else:
        raise ValueError(f"Unsupported semantic kind: {kind}")
    return module.analyze(metadata, contract)


def _normalize_semantics(semantic: dict | None) -> dict[str, dict]:
    """Accept either the legacy single report or a requirement-keyed evidence map."""
    if not semantic:
        return {}
    if "release_decision" in semantic:
        requirement_id = semantic.get("requirement_id")
        if not requirement_id:
            raise ValueError("Single semantic evidence must include requirement_id")
        return {requirement_id: semantic}
    return semantic


def analyze(changed: list[str], manifest: dict, semantic: dict | None = None) -> dict:
    changed_set = set(changed)
    impacted = []
    for control in manifest.get("controls", []):
        matched = sorted(changed_set.intersection(control.get("components", [])))
        if matched:
            impacted.append({
                "requirement_id": control["requirement_id"],
                "risk": control["risk"],
                "matched_components": matched,
                "selected_evidence": control.get("evidence", []),
                "skipped_evidence": control.get("not_relevant", []),
            })

    semantic_map = _normalize_semantics(semantic)
    impacted_ids = [control["requirement_id"] for control in impacted]
    relevant_semantics = {rid: semantic_map[rid] for rid in impacted_ids if rid in semantic_map}
    missing_semantics = [rid for rid in impacted_ids if rid not in relevant_semantics]
    no_go_ids = [
        rid for rid, evidence in relevant_semantics.items()
        if evidence.get("release_decision") == "NO-GO"
    ]

    if not impacted:
        decision = "NO-IMPACT"
        reason = "No changed file maps to a frozen business control in the current manifest."
    elif no_go_ids:
        decision = "NO-GO"
        reason = "Business-intent drift detected in: " + ", ".join(no_go_ids) + "."
    elif missing_semantics:
        decision = "REVIEW"
        reason = "Impacted controls still require semantic evidence: " + ", ".join(missing_semantics) + "."
    else:
        decision = "GO"
        reason = "All impacted business controls with required semantic checks align with frozen intent."

    return {
        "schema_version": "1.1",
        "changed_files": sorted(changed),
        "impacted_controls": impacted,
        "impact_count": len(impacted),
        "semantic_evidence": relevant_semantics,
        "missing_semantic_evidence": missing_semantics,
        "decision": decision,
        "reason": reason,
    }


def _render_semantic(lines: list[str], requirement_id: str, semantic: dict) -> None:
    lines.append(f"  {requirement_id}:")
    if "expected_threshold" in semantic:
        lines += [
            f"    contract threshold: >{semantic['expected_threshold']:.0f}%",
            f"    metadata threshold: >{semantic['observed_threshold']:.0f}%",
        ]
    elif "expected_logic" in semantic:
        lines += [
            f"    contract logic: {semantic['expected_logic'].upper()}",
            f"    metadata logic: {semantic['observed_logic'].upper()}",
            f"    conditions aligned: {semantic['conditions_aligned']}",
        ]
    elif "permission_set" in semantic:
        lines.append(f"    permission set: {semantic['permission_set']}")
        for row in semantic["field_permissions"]:
            lines.append(
                f"    {row['field']}: readable={row['observed']['readable']} "
                f"editable={row['observed']['editable']} intent_match={row['matches_intent']}"
            )
    lines.append(f"    mismatches: {semantic['mismatch_count']}")
    lines.append(f"    decision: {semantic['release_decision']}")


def render_text(report: dict) -> str:
    lines = ["PR IMPACT", "", "Changed:"]
    lines.extend(f"  {p}" for p in report["changed_files"])
    lines += ["", "Affected business controls:"]
    if not report["impacted_controls"]:
        lines.append("  none")
    for control in report["impacted_controls"]:
        lines.append(f"  {control['requirement_id']}  {control['risk'].upper()} RISK")
        lines.append("    matched:")
        lines.extend(f"      - {p}" for p in control["matched_components"])
        lines.append("    selected evidence:")
        for item in control["selected_evidence"]:
            marker = "✓" if item["kind"] == "required" else "→"
            suffix = f" — {item.get('reason', '')}" if item.get("reason") else ""
            lines.append(f"      {marker} {item['label']}{suffix}")
        if control["skipped_evidence"]:
            lines.append("    not selected:")
            for item in control["skipped_evidence"]:
                lines.append(f"      - {item['label']} — {item['reason']}")

    semantics = report.get("semantic_evidence", {})
    if semantics:
        lines += ["", "Semantic evidence:"]
        for requirement_id in sorted(semantics):
            _render_semantic(lines, requirement_id, semantics[requirement_id])

    missing = report.get("missing_semantic_evidence", [])
    if missing:
        lines += ["", "Semantic evidence still required:"]
        lines.extend(f"  - {requirement_id}" for requirement_id in missing)

    lines += ["", f"Decision: {report['decision']}", f"Reason: {report['reason']}"]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=Path("impact/manifest.json"))
    changed_group = parser.add_mutually_exclusive_group(required=True)
    changed_group.add_argument("--changed", nargs="+")
    changed_group.add_argument("--changed-file", type=Path)
    parser.add_argument(
        "--semantic-control",
        action="append",
        nargs=4,
        metavar=("REQUIREMENT_ID", "KIND", "METADATA", "CONTRACT"),
        help="Repeatable semantic check: requirement ID, kind, metadata path, contract path.",
    )
    parser.add_argument("--semantic-metadata", type=Path)
    parser.add_argument("--semantic-kind", choices=SEMANTIC_KINDS, default="validation-rule")
    parser.add_argument("--contract", type=Path, default=Path("policies/SF-OPP-001.json"))
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--text-out", type=Path)
    args = parser.parse_args()

    changed = args.changed if args.changed is not None else load_changed_file(args.changed_file)
    semantic_map: dict[str, dict] = {}

    if args.semantic_control:
        for requirement_id, kind, metadata, contract in args.semantic_control:
            if kind not in SEMANTIC_KINDS:
                parser.error(f"Unsupported semantic kind for {requirement_id}: {kind}")
            semantic_map[requirement_id] = run_semantic(Path(metadata), Path(contract), kind)

    if args.semantic_metadata:
        legacy = run_semantic(args.semantic_metadata, args.contract, args.semantic_kind)
        semantic_map[legacy["requirement_id"]] = legacy

    report = analyze(changed, load_json(args.manifest), semantic_map)
    rendered = render_text(report)
    print(rendered)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if args.text_out:
        args.text_out.parent.mkdir(parents=True, exist_ok=True)
        args.text_out.write_text(rendered + "\n", encoding="utf-8")
    return 2 if report["decision"] == "NO-GO" else 0


if __name__ == "__main__":
    raise SystemExit(main())
