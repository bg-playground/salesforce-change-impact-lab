#!/usr/bin/env python3
"""Deterministic PR-aware Salesforce business-impact selector."""
from __future__ import annotations
import argparse
import importlib.util
import json
import sys
from pathlib import Path


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_changed_file(path: Path) -> list[str]:
    """Load one repository-relative changed path per line."""
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def run_semantic(metadata: Path, contract: Path) -> dict:
    tool = Path(__file__).with_name("impact_lab.py")
    spec = importlib.util.spec_from_file_location("impact_lab_for_pr", tool)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.analyze(metadata, contract)


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

    if semantic and impacted:
        decision = semantic["release_decision"]
        reason = semantic["decision_reason"]
    elif impacted:
        decision = "REVIEW"
        reason = "Business-control impact detected; run the selected evidence before release."
    else:
        decision = "NO-IMPACT"
        reason = "No changed file maps to a frozen business control in the current manifest."

    return {
        "schema_version": "1.0",
        "changed_files": sorted(changed),
        "impacted_controls": impacted,
        "impact_count": len(impacted),
        "semantic_evidence": semantic,
        "decision": decision,
        "reason": reason,
    }


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
    semantic = report.get("semantic_evidence")
    if semantic:
        lines += [
            "",
            "Semantic evidence:",
            f"  contract threshold: >{semantic['expected_threshold']:.0f}%",
            f"  metadata threshold: >{semantic['observed_threshold']:.0f}%",
            f"  mismatches: {semantic['mismatch_count']}",
        ]
    lines += ["", f"Decision: {report['decision']}", f"Reason: {report['reason']}"]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=Path("impact/manifest.json"))
    changed_group = parser.add_mutually_exclusive_group(required=True)
    changed_group.add_argument("--changed", nargs="+")
    changed_group.add_argument("--changed-file", type=Path)
    parser.add_argument("--semantic-metadata", type=Path)
    parser.add_argument("--contract", type=Path, default=Path("policies/SF-OPP-001.json"))
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--text-out", type=Path)
    args = parser.parse_args()

    changed = args.changed if args.changed is not None else load_changed_file(args.changed_file)
    semantic = run_semantic(args.semantic_metadata, args.contract) if args.semantic_metadata else None
    report = analyze(changed, load_json(args.manifest), semantic)
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
