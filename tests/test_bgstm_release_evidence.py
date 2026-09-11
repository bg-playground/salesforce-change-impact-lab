import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "bgstm_release_evidence", ROOT / "tools" / "bgstm_release_evidence.py"
)
bgstm = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = bgstm
SPEC.loader.exec_module(bgstm)

PROJECT_ID = "00000000-0000-0000-0000-000000000039"


def pr_impact(decision="GO", *, flow_decision="GO", missing=None):
    return {
        "decision": decision,
        "missing_semantic_evidence": missing or [],
        "semantic_evidence": {
            "SF-CASE-001": {
                "requirement_id": "SF-CASE-001",
                "release_decision": flow_decision,
                "mismatch_count": 0 if flow_decision == "GO" else 2,
            },
            "SF-OPP-001": {
                "requirement_id": "SF-OPP-001",
                "release_decision": "GO",
                "mismatch_count": 0,
            },
        },
    }


class BgstmReleaseEvidenceTests(unittest.TestCase):
    def build(self, impact, code="passed", apex="passed"):
        return bgstm.build_bundle(
            impact,
            project_id=PROJECT_ID,
            git_sha="abc123",
            git_branch="feature/test",
            ci_url="https://github.com/example/repo/actions/runs/1",
            code_analyzer=code,
            apex_runtime=apex,
        )

    def test_all_required_evidence_passes_go(self):
        bundle = self.build(pr_impact())
        self.assertEqual("GO", bundle["release_decision"])
        self.assertEqual("passed", bundle["bgstm_external_results_v1"]["finish_session_request"]["status"])
        self.assertEqual(4, len(bundle["bgstm_external_results_v1"]["case_templates"]))

    def test_semantic_no_go_cannot_be_masked_by_passing_supporting_signals(self):
        bundle = self.build(pr_impact("NO-GO", flow_decision="NO-GO"))
        self.assertEqual("NO-GO", bundle["release_decision"])
        flow = next(
            c for c in bundle["bgstm_external_results_v1"]["case_templates"]
            if c["requirement_external_ids"] == ["SF-CASE-001"]
        )
        self.assertEqual("failed", flow["outcome"])
        self.assertIn("mismatches=2", flow["error_message"])

    def test_missing_required_supporting_evidence_is_review(self):
        bundle = self.build(pr_impact(), apex="not-run")
        self.assertEqual("REVIEW", bundle["release_decision"])
        self.assertEqual("aborted", bundle["bgstm_external_results_v1"]["finish_session_request"]["status"])

    def test_failed_code_analyzer_blocks_release(self):
        bundle = self.build(pr_impact(), code="failed")
        self.assertEqual("NO-GO", bundle["release_decision"])
        self.assertIn("Code Analyzer", bundle["release_reason"])

    def test_missing_semantic_evidence_is_review(self):
        impact = pr_impact("REVIEW", missing=["SF-SEC-001"])
        bundle = self.build(impact)
        self.assertEqual("REVIEW", bundle["release_decision"])
        self.assertIn("SF-SEC-001", bundle["release_reason"])

    def test_bgstm_case_templates_use_requirement_external_ids(self):
        bundle = self.build(pr_impact())
        semantic = [
            c for c in bundle["bgstm_external_results_v1"]["case_templates"]
            if c["source"]["kind"] == "semantic"
        ]
        self.assertEqual(
            [["SF-CASE-001"], ["SF-OPP-001"]],
            [c["requirement_external_ids"] for c in semantic],
        )
        self.assertTrue(all(c["external_id"].startswith("salesforce-change-impact-lab:") for c in semantic))


if __name__ == "__main__":
    unittest.main()
