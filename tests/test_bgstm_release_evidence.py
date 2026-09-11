import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("bgstm_release_evidence", ROOT / "tools" / "bgstm_release_evidence.py")
bgstm = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = bgstm
SPEC.loader.exec_module(bgstm)
PROJECT_ID = "00000000-0000-0000-0000-000000000039"
SHA = "abc123"


def pr_impact(decision="GO", *, flow_decision="GO", missing=None):
    return {"decision": decision, "missing_semantic_evidence": missing or [], "semantic_evidence": {
        "SF-CASE-001": {"requirement_id": "SF-CASE-001", "release_decision": flow_decision,
                        "mismatch_count": 0 if flow_decision == "GO" else 2},
        "SF-OPP-001": {"requirement_id": "SF-OPP-001", "release_decision": "GO", "mismatch_count": 0}}}


def code_evidence(status="passed", sha=SHA):
    return {"schema": bgstm.SUPPORTING_SCHEMA, "source": "salesforce-code-analyzer", "status": status,
            "git_sha": sha, "run_id": "1", "run_url": "https://github.com/example/repo/actions/runs/1",
            "summary": {"exit_code": 0 if status == "passed" else 1}}


class BgstmReleaseEvidenceTests(unittest.TestCase):
    def build(self, impact, code=None, apex="passed"):
        return bgstm.build_bundle(impact, project_id=PROJECT_ID, git_sha=SHA, git_branch="feature/test",
                                  ci_url="https://github.com/example/repo/actions/runs/1",
                                  code_analyzer_evidence=code or {**code_evidence(), "validation": "accepted"},
                                  apex_runtime=apex)

    def test_all_required_evidence_passes_go(self):
        bundle = self.build(pr_impact())
        self.assertEqual("GO", bundle["release_decision"])
        self.assertEqual(4, len(bundle["bgstm_external_results_v1"]["case_templates"]))

    def test_semantic_no_go_cannot_be_masked(self):
        self.assertEqual("NO-GO", self.build(pr_impact("NO-GO", flow_decision="NO-GO"))["release_decision"])

    def test_failed_code_analyzer_blocks_release(self):
        bundle = self.build(pr_impact(), {**code_evidence("failed"), "validation": "accepted"})
        self.assertEqual("NO-GO", bundle["release_decision"])

    def test_missing_required_supporting_evidence_is_review(self):
        self.assertEqual("REVIEW", self.build(pr_impact(), apex="not-run")["release_decision"])

    def test_missing_semantic_evidence_is_review(self):
        self.assertEqual("REVIEW", self.build(pr_impact("REVIEW", missing=["SF-SEC-001"]))["release_decision"])

    def test_evidence_file_passed_is_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "code.json"
            path.write_text(json.dumps(code_evidence()), encoding="utf-8")
            result = bgstm.load_supporting_evidence(path, source="salesforce-code-analyzer", expected_sha=SHA)
        self.assertEqual("passed", result["status"])
        self.assertEqual("accepted", result["validation"])

    def test_missing_evidence_is_not_run(self):
        result = bgstm.load_supporting_evidence(None, source="salesforce-code-analyzer", expected_sha=SHA)
        self.assertEqual("not-run", result["status"])
        self.assertEqual("missing", result["validation"])

    def test_malformed_evidence_is_not_trusted(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "code.json"
            path.write_text("not json", encoding="utf-8")
            result = bgstm.load_supporting_evidence(path, source="salesforce-code-analyzer", expected_sha=SHA)
        self.assertEqual("not-run", result["status"])
        self.assertEqual("malformed", result["validation"])

    def test_sha_mismatch_is_not_trusted(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "code.json"
            path.write_text(json.dumps(code_evidence(sha="other")), encoding="utf-8")
            result = bgstm.load_supporting_evidence(path, source="salesforce-code-analyzer", expected_sha=SHA)
        self.assertEqual("not-run", result["status"])
        self.assertEqual("sha-mismatch", result["validation"])

    def test_code_analyzer_case_preserves_ingested_provenance(self):
        bundle = self.build(pr_impact())
        case = next(c for c in bundle["bgstm_external_results_v1"]["case_templates"] if c["source"]["kind"] == "code-analyzer")
        self.assertEqual("accepted", case["source"]["validation"])
        self.assertEqual(SHA, case["source"]["git_sha"])


if __name__ == "__main__":
    unittest.main()
