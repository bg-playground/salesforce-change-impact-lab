#!/usr/bin/env python3
"""Emit SHA-bound Apex/runtime supporting evidence for the release bundle.

This utility does not run Salesforce tests. An authenticated workflow supplies the
result of a real runtime command and this tool serializes it into the shared
supporting-evidence contract.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

SCHEMA = "salesforce-change-impact-lab.supporting-evidence.v1"
SOURCE = "salesforce-apex-runtime"


def build_evidence(*, status: str, git_sha: str, runtime_kind: str, run_id: str | None,
                   run_url: str | None, total: int | None, passed: int | None,
                   failed: int | None, fixture: bool = False) -> dict:
    if status not in {"passed", "failed"}:
        raise ValueError(f"Unsupported runtime status: {status}")
    return {
        "schema": SCHEMA,
        "source": SOURCE,
        "status": status,
        "git_sha": git_sha,
        "run_id": run_id,
        "run_url": run_url,
        "summary": {
            "runtime_kind": runtime_kind,
            "total": total,
            "passed": passed,
            "failed": failed,
            "fixture": fixture,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--status", choices=("passed", "failed"), required=True)
    parser.add_argument("--git-sha", required=True)
    parser.add_argument("--runtime-kind", default="apex-tests")
    parser.add_argument("--run-id")
    parser.add_argument("--run-url")
    parser.add_argument("--total", type=int)
    parser.add_argument("--passed", type=int)
    parser.add_argument("--failed", type=int)
    parser.add_argument("--fixture", action="store_true")
    parser.add_argument("--json-out", type=Path, required=True)
    args = parser.parse_args()

    payload = build_evidence(
        status=args.status,
        git_sha=args.git_sha,
        runtime_kind=args.runtime_kind,
        run_id=args.run_id,
        run_url=args.run_url,
        total=args.total,
        passed=args.passed,
        failed=args.failed,
        fixture=args.fixture,
    )
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
