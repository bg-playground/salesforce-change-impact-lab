#!/usr/bin/env python3
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
import xml.etree.ElementTree as ET

NS = {"sf": "http://soap.sforce.com/2006/04/metadata"}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def extract(permission_set_path: Path) -> dict[str, dict[str, bool]]:
    root = ET.parse(permission_set_path).getroot()
    observed: dict[str, dict[str, bool]] = {}
    for node in root.findall("sf:fieldPermissions", NS):
        field = node.findtext("sf:field", default="", namespaces=NS)
        if not field:
            continue
        observed[field] = {
            "readable": (node.findtext("sf:readable", default="false", namespaces=NS) or "false").lower() == "true",
            "editable": (node.findtext("sf:editable", default="false", namespaces=NS) or "false").lower() == "true",
        }
    return observed


def analyze(permission_set_path: Path, contract_path: Path) -> dict:
    contract = load_json(contract_path)
    observed = extract(permission_set_path)
    mismatches = []
    rows = []

    for expected in contract["field_permissions"]:
        field = expected["field"]
        actual = observed.get(field, {"readable": False, "editable": False})
        for permission in ("readable", "editable"):
            if actual[permission] != expected[permission]:
                mismatches.append({
                    "field": field,
                    "permission": permission,
                    "expected": expected[permission],
                    "observed": actual[permission],
                })
        rows.append({
            "field": field,
            "expected": {"readable": expected["readable"], "editable": expected["editable"]},
            "observed": actual,
            "matches_intent": actual == {"readable": expected["readable"], "editable": expected["editable"]},
        })

    decision = "GO" if not mismatches else "NO-GO"
    return {
        "schema_version": "1.0",
        "requirement_id": contract["requirement_id"],
        "risk": contract["risk"],
        "permission_set": contract["permission_set"],
        "field_permissions": rows,
        "mismatches": mismatches,
        "mismatch_count": len(mismatches),
        "release_decision": decision,
        "decision_reason": (
            "Permission Set field access matches frozen least-privilege intent."
            if decision == "GO"
            else "Permission Set field access diverges from frozen least-privilege intent."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--permission-set", required=True, type=Path)
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()
    report = analyze(args.permission_set, args.contract)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    finance = next((row for row in report["field_permissions"] if row["field"] == "Opportunity.Finance_Approved__c"), None)
    observed_edit = finance["observed"]["editable"] if finance else None
    print(
        f"{report['requirement_id']}: {report['release_decision']} | "
        f"Finance_Approved__c editable={observed_edit} | mismatches={report['mismatch_count']}"
    )
    return 0 if report["release_decision"] == "GO" else 2


if __name__ == "__main__":
    sys.exit(main())
