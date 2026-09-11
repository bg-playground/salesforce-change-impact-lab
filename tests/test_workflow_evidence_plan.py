import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "workflow_evidence_plan", ROOT / "tools" / "workflow_evidence_plan.py"
)
planmod = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = planmod
SPEC.loader.exec_module(planmod)

SHA = "abc123"


def run(run_id, *, sha=SHA, conclusion="success", attempt=1, status="completed", updated="2026-09-11T20:00:00Z"):
    return {
        "id": run_id,
        "name": "workflow",
        "head_sha": sha,
        "status": status,
        "conclusion": conclusion,
        "run_attempt": attempt,
        "html_url": f"https://github.com/example/repo/actions/runs/{run_id}",
        "created_at": "2026-09-11T19:00:00Z",
        "updated_at": updated,
    }


class WorkflowEvidencePlanTests(unittest.TestCase):
    def test_both_sources_found(self):
        plan = planmod.build_plan(
            expected_sha=SHA,
            pr_impact_runs=[run(10)],
            code_analyzer_runs=[run(20)],
        )
        self.assertEqual([], plan["missing_sources"])
        self.assertEqual(10, plan["sources"]["pr_change_impact"]["run"]["id"])
        self.assertEqual(20, plan["sources"]["salesforce_code_analyzer"]["run"]["id"])

    def test_one_source_missing(self):
        plan = planmod.build_plan(
            expected_sha=SHA,
            pr_impact_runs=[run(10)],
            code_analyzer_runs=[],
        )
        self.assertEqual(["salesforce_code_analyzer"], plan["missing_sources"])

    def test_failed_upstream_is_still_selected(self):
        selected = planmod.select_run([run(10, conclusion="failure")], expected_sha=SHA)
        self.assertEqual("failure", selected["conclusion"])
        self.assertEqual(10, selected["id"])

    def test_wrong_sha_is_not_selected(self):
        selected = planmod.select_run([run(10, sha="other")], expected_sha=SHA)
        self.assertIsNone(selected)

    def test_incomplete_run_is_not_selected(self):
        selected = planmod.select_run([run(10, status="in_progress")], expected_sha=SHA)
        self.assertIsNone(selected)

    def test_latest_rerun_attempt_wins(self):
        selected = planmod.select_run(
            [
                run(10, attempt=1, updated="2026-09-11T20:00:00Z"),
                run(10, attempt=2, updated="2026-09-11T20:05:00Z"),
            ],
            expected_sha=SHA,
        )
        self.assertEqual(2, selected["run_attempt"])

    def test_newer_completed_run_wins_when_attempts_equal(self):
        selected = planmod.select_run(
            [
                run(10, updated="2026-09-11T20:00:00Z"),
                run(11, updated="2026-09-11T20:05:00Z"),
            ],
            expected_sha=SHA,
        )
        self.assertEqual(11, selected["id"])


if __name__ == "__main__":
    unittest.main()
