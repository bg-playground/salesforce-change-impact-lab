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


def supporting(source, status="passed", sha=SHA):
    return {"schema": bgstm.SUPPORTING_SCHEMA, "source": source, "status": status,
            "git_sha": sha, "run_id": "1", "run_url": "https://github.com/example/repo/actions/runs/1",
            "summary": {"fixture": True}}


def accepted(source, status="passed", sha=SHA):
    return {**supporting(source, status, sha), "validation": "accepted"}


class BgstmReleaseEvidenceTests(unittest.TestCase):
    def build(self, impact, code=None, apex=None):
        return bgstm.build_bundle(
            impact,
            project_id=PROJECT_ID,
            git_sha=SHA,
            git_branch="feature/test",
            ci_url="https://github.com/example/repo/actions/runs/1",
            code_analyzer_evidence=code or accepted("salesforce-code-analyzer"),
            apex_runtime_evidence=apex or accepted("salesforce-apex-runtime"),
        )

    def test_all_required_evidence_passes_go(self):
        self.assertEqual("GO", self.build(pr_impact())["release_decision"])

    def test_semantic_no_go_cannot_be_masked(self):
        self.assertEqual("NO-GO", self.build(pr_impact("NO-GO", flow_decision="NO-GO"))["release_decision"])

    def test_failed_code_analyzer_blocks_release(self):
        self.assertEqual("NO-GO", self.build(pr_impact(), code=accepted("salesforce-code-analyzer", "failed"))["release_decision"])

    def test_failed_apex_runtime_blocks_release(self):
        self.assertEqual("NO-GO", self.build(pr_impact(), apex=accepted("salesforce-apex-runtime", "failed"))["release_decision"])

    def test_missing_apex_runtime_is_review(self):
        missing = {"source": "salesforce-apex-runtime", "status": "not-run", "validation": "missing"}
        self.assertEqual("REVIEW", self.build(pr_impact(), apex=missing)["release_decision"])

    def _load(self, payload, source="salesforce-apex-runtime"):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "evidence.json"
            if isinstance(payload, str):
                path.write_text(payload, encoding="utf-8")
            else:
                path.write_text(json.dumps(payload), encoding="utf-8")
            return bgstm.load_supporting_evidence(path, source=source, expected_sha=SHA)

    def test_apex_passed_evidence_is_accepted(self):
        result = self._load(supporting("salesforce-apex-runtime"))
        self.assertEqual(("passed", "accepted"), (result["status"], result["validation"]))

    def test_apex_failed_evidence_is_accepted(self):
        result = self._load(supporting("salesforce-apex-runtime", "failed"))
        self.assertEqual(("failed", "accepted"), (result["status"], result["validation"]))

    def test_missing_apex_evidence_is_not_run(self):
        result = bgstm.load_supporting_evidence(None, source="salesforce-apex-runtime", expected_sha=SHA)
        self.assertEqual(("not-run", "missing"), (result["status"], result["validation"]))

    def test_malformed_apex_evidence_is_not_trusted(self):
        result = self._load("not json")
        self.assertEqual(("not-run", "malformed"), (result["status"], result["validation"]))

    def test_wrong_source_apex_evidence_is_not_trusted(self):
        result = self._load(supporting("salesforce-code-analyzer"))
        self.assertEqual(("not-run", "malformed"), (result["status"], result["validation"]))

    def test_apex_sha_mismatch_is_not_trusted(self):
        result = self._load(supporting("salesforce-apex-runtime", sha="other"))
        self.assertEqual(("not-run", "sha-mismatch"), (result["status"], result["validation"]))

    def test_both_supporting_cases_preserve_provenance(self):
        bundle = self.build(pr_impact())
        supporting_cases = [c for c in bundle["bgstm_external_results_v1"]["case_templates"] if c["source"]["kind"] in {"code-analyzer", "apex-runtime"}]
        self.assertEqual(2, len(supporting_cases))
        self.assertTrue(all(c["source"]["validation"] == "accepted" for c in supporting_cases))
        self.assertTrue(all(c["source"]["git_sha"] == SHA for c in supporting_cases))


if __name__ == "__main__":
    unittest.main()
