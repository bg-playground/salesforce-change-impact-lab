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
        self.flow = "force-app/main/default/flows/Case_Strategic_Escalation.flow-meta.xml"
        self.flow_contract = ROOT / "policies" / "SF-CASE-001.json"
        self.flow_baseline = ROOT / self.flow
        self.flow_mutant = ROOT / "mutations" / "Case_Strategic_Escalation.logic-or.flow-meta.xml"
        self.permission_set = "force-app/main/default/permissionsets/Sales_Rep_Opportunity_Access.permissionset-meta.xml"
        self.permission_contract = ROOT / "policies" / "SF-SEC-001.json"
        self.permission_baseline = ROOT / self.permission_set
        self.permission_mutant = ROOT / "mutations" / "Sales_Rep_Opportunity_Access.finance-edit.permissionset-meta.xml"

    def evidence_map(self, *reports):
        return {report["requirement_id"]: report for report in reports}

    def test_unrelated_change_is_no_impact(self):
        report = pr_impact.analyze(["README.md"], self.manifest)
        self.assertEqual("NO-IMPACT", report["decision"])
        self.assertEqual(0, report["impact_count"])

    def test_relevant_change_selects_high_risk_control(self):
        report = pr_impact.analyze([self.rule], self.manifest)
        self.assertEqual("REVIEW", report["decision"])
        self.assertEqual(["SF-OPP-001"], report["missing_semantic_evidence"])
        self.assertEqual("SF-OPP-001", report["impacted_controls"][0]["requirement_id"])
        self.assertEqual("high", report["impacted_controls"][0]["risk"])
        labels = [e["label"] for e in report["impacted_controls"][0]["selected_evidence"]]
        self.assertIn("semantic contract check", labels)
        self.assertIn("Apex OpportunityReleaseGuardTest", labels)

    def test_baseline_semantics_make_impacted_change_go(self):
        semantic = pr_impact.run_semantic(self.baseline, self.contract)
        report = pr_impact.analyze([self.rule], self.manifest, semantic)
        self.assertEqual("GO", report["decision"])
        self.assertEqual(0, report["semantic_evidence"]["SF-OPP-001"]["mismatch_count"])

    def test_mutant_semantics_make_impacted_change_no_go(self):
        semantic = pr_impact.run_semantic(self.mutant, self.contract)
        report = pr_impact.analyze([self.rule], self.manifest, semantic)
        evidence = report["semantic_evidence"]["SF-OPP-001"]
        self.assertEqual("NO-GO", report["decision"])
        self.assertEqual(30, evidence["observed_threshold"])
        self.assertGreater(evidence["mismatch_count"], 0)

    def test_flow_baseline_semantics_make_impacted_change_go(self):
        semantic = pr_impact.run_semantic(self.flow_baseline, self.flow_contract, "flow")
        report = pr_impact.analyze([self.flow], self.manifest, semantic)
        evidence = report["semantic_evidence"]["SF-CASE-001"]
        self.assertEqual("GO", report["decision"])
        self.assertEqual("and", evidence["observed_logic"])
        self.assertEqual(0, evidence["mismatch_count"])
        self.assertIn("contract logic: AND", pr_impact.render_text(report))

    def test_flow_mutant_semantics_make_impacted_change_no_go(self):
        semantic = pr_impact.run_semantic(self.flow_mutant, self.flow_contract, "flow")
        report = pr_impact.analyze([self.flow], self.manifest, semantic)
        evidence = report["semantic_evidence"]["SF-CASE-001"]
        self.assertEqual("NO-GO", report["decision"])
        self.assertEqual("or", evidence["observed_logic"])
        self.assertGreater(evidence["mismatch_count"], 0)

    def test_permission_baseline_semantics_make_impacted_change_go(self):
        semantic = pr_impact.run_semantic(self.permission_baseline, self.permission_contract, "permission-set")
        report = pr_impact.analyze([self.permission_set], self.manifest, semantic)
        self.assertEqual("GO", report["decision"])
        self.assertEqual("SF-SEC-001", report["impacted_controls"][0]["requirement_id"])
        self.assertEqual(0, report["semantic_evidence"]["SF-SEC-001"]["mismatch_count"])
        self.assertIn("Finance_Approved__c", pr_impact.render_text(report))

    def test_permission_mutant_semantics_make_impacted_change_no_go(self):
        semantic = pr_impact.run_semantic(self.permission_mutant, self.permission_contract, "permission-set")
        report = pr_impact.analyze([self.permission_set], self.manifest, semantic)
        self.assertEqual("NO-GO", report["decision"])
        self.assertEqual(1, report["semantic_evidence"]["SF-SEC-001"]["mismatch_count"])

    def test_multiple_controls_all_go(self):
        opportunity = pr_impact.run_semantic(self.baseline, self.contract)
        flow = pr_impact.run_semantic(self.flow_baseline, self.flow_contract, "flow")
        permission = pr_impact.run_semantic(self.permission_baseline, self.permission_contract, "permission-set")
        report = pr_impact.analyze(
            [self.rule, self.flow, self.permission_set],
            self.manifest,
            self.evidence_map(opportunity, flow, permission),
        )
        self.assertEqual(3, report["impact_count"])
        self.assertEqual("GO", report["decision"])
        self.assertEqual([], report["missing_semantic_evidence"])
        self.assertEqual(
            {"SF-OPP-001", "SF-CASE-001", "SF-SEC-001"},
            set(report["semantic_evidence"]),
        )

    def test_one_no_go_blocks_multi_control_release(self):
        opportunity = pr_impact.run_semantic(self.baseline, self.contract)
        flow = pr_impact.run_semantic(self.flow_mutant, self.flow_contract, "flow")
        report = pr_impact.analyze(
            [self.rule, self.flow],
            self.manifest,
            self.evidence_map(opportunity, flow),
        )
        self.assertEqual("NO-GO", report["decision"])
        self.assertIn("SF-CASE-001", report["reason"])
        self.assertEqual("GO", report["semantic_evidence"]["SF-OPP-001"]["release_decision"])
        self.assertEqual("NO-GO", report["semantic_evidence"]["SF-CASE-001"]["release_decision"])

    def test_missing_semantics_keeps_multi_control_change_in_review(self):
        opportunity = pr_impact.run_semantic(self.baseline, self.contract)
        report = pr_impact.analyze(
            [self.rule, self.flow],
            self.manifest,
            self.evidence_map(opportunity),
        )
        self.assertEqual("REVIEW", report["decision"])
        self.assertEqual(["SF-CASE-001"], report["missing_semantic_evidence"])

    def test_no_go_takes_precedence_over_missing_semantics(self):
        opportunity = pr_impact.run_semantic(self.mutant, self.contract)
        report = pr_impact.analyze(
            [self.rule, self.flow],
            self.manifest,
            self.evidence_map(opportunity),
        )
        self.assertEqual("NO-GO", report["decision"])
        self.assertEqual(["SF-CASE-001"], report["missing_semantic_evidence"])

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
