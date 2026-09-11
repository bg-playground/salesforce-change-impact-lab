#!/usr/bin/env python3
"""Deterministic PR-aware Salesforce business-impact selector."""
from __future__ import annotations
import argparse, json
from pathlib import Path


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def analyze(changed: list[str], manifest: dict) -> dict:
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
    decision = "REVIEW" if impacted else "NO-IMPACT"
    return {
        "schema_version": "1.0",
        "changed_files": sorted(changed),
        "impacted_controls": impacted,
        "impact_count": len(impacted),
        "decision": decision,
        "reason": (
            "Business-control impact detected; run the selected evidence before release."
            if impacted else
            "No changed file maps to a frozen business control in the current manifest."
        ),
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
            suffix = f" — {item.get('reason','')}" if item.get("reason") else ""
            lines.append(f"      {marker} {item['label']}{suffix}")
        if control["skipped_evidence"]:
            lines.append("    not selected:")
            for item in control["skipped_evidence"]:
                lines.append(f"      - {item['label']} — {item['reason']}")
    lines += ["", f"Decision: {report['decision']}", f"Reason: {report['reason']}"]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=Path("impact/manifest.json"))
    parser.add_argument("--changed", nargs="+", required=True)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()
    report = analyze(args.changed, load_json(args.manifest))
    print(render_text(report))
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
