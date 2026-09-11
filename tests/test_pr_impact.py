import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("pr_impact", ROOT / "tools" / "pr_impact.py")
pr_impact = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = pr_impact
SPEC.loader.exec_module(pr_impact)


class PrImpactTests(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads((ROOT / "impact" / "manifest.json").read_text(encoding="utf-8"))
        self.rule = "force-app/main/default/objects/Opportunity/validationRules/High_Discount_Requires_Finance.validationRule-meta.xml"
        self.contract = ROOT / "policies" / "SF-OPP-001.json"
        self.baseline = ROOT / self.rule
        self.mutant = ROOT / "mutations" / "High_Discount_Requires_Finance.threshold-30.validationRule-meta.xml"

    def test_unrelated_change_is_no_impact(self):
        report = pr_impact.analyze(["README.md"], self.manifest)
        self.assertEqual("NO-IMPACT", report["decision"])
        self.assertEqual(0, report["impact_count"])

    def test_relevant_change_selects_high_risk_control(self):
        report = pr_impact.analyze([self.rule], self.manifest)
        self.assertEqual("REVIEW", report["decision"])
        self.assertEqual("SF-OPP-001", report["impacted_controls"][0]["requirement_id"])
        self.assertEqual("high", report["impacted_controls"][0]["risk"])
        labels = [e["label"] for e in report["impacted_controls"][0]["selected_evidence"]]
        self.assertIn("semantic contract check", labels)
        self.assertIn("Apex OpportunityReleaseGuardTest", labels)

    def test_baseline_semantics_make_impacted_change_go(self):
        semantic = pr_impact.run_semantic(self.baseline, self.contract)
        report = pr_impact.analyze([self.rule], self.manifest, semantic)
        self.assertEqual("GO", report["decision"])
        self.assertEqual(0, report["semantic_evidence"]["mismatch_count"])

    def test_mutant_semantics_make_impacted_change_no_go(self):
        semantic = pr_impact.run_semantic(self.mutant, self.contract)
        report = pr_impact.analyze([self.rule], self.manifest, semantic)
        self.assertEqual("NO-GO", report["decision"])
        self.assertEqual(30, report["semantic_evidence"]["observed_threshold"])
        self.assertGreater(report["semantic_evidence"]["mismatch_count"], 0)

    def test_multi_file_change_deduplicates_control(self):
        report = pr_impact.analyze([
            self.rule,
            "force-app/main/default/objects/Opportunity/fields/Finance_Approved__c.field-meta.xml",
            "README.md",
        ], self.manifest)
        self.assertEqual(1, report["impact_count"])
        self.assertEqual(2, len(report["impacted_controls"][0]["matched_components"]))

    def test_changed_file_loader_normalizes_blank_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            changed_file = Path(tmp) / "changed-files.txt"
            changed_file.write_text(f"README.md\n\n{self.rule}\n", encoding="utf-8")
            self.assertEqual(["README.md", self.rule], pr_impact.load_changed_file(changed_file))


if __name__ == "__main__":
    unittest.main()
