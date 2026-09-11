import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("permission_impact", ROOT / "tools" / "permission_impact.py")
permission_impact = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = permission_impact
SPEC.loader.exec_module(permission_impact)


class PermissionImpactTests(unittest.TestCase):
    def setUp(self):
        self.contract = ROOT / "policies" / "SF-SEC-001.json"
        self.baseline = ROOT / "tests" / "fixtures" / "baseline" / "Sales_Rep_Opportunity_Access.permissionset-meta.xml"
        self.mutant = ROOT / "mutations" / "Sales_Rep_Opportunity_Access.finance-edit.permissionset-meta.xml"

    def test_baseline_is_go(self):
        report = permission_impact.analyze(self.baseline, self.contract)
        self.assertEqual("GO", report["release_decision"])
        self.assertEqual(0, report["mismatch_count"])

    def test_finance_approval_is_read_only_in_baseline(self):
        report = permission_impact.analyze(self.baseline, self.contract)
        finance = next(row for row in report["field_permissions"] if row["field"] == "Opportunity.Finance_Approved__c")
        self.assertTrue(finance["observed"]["readable"])
        self.assertFalse(finance["observed"]["editable"])
        self.assertTrue(finance["matches_intent"])

    def test_finance_edit_mutation_is_no_go(self):
        report = permission_impact.analyze(self.mutant, self.contract)
        self.assertEqual("NO-GO", report["release_decision"])
        self.assertEqual(1, report["mismatch_count"])
        mismatch = report["mismatches"][0]
        self.assertEqual("Opportunity.Finance_Approved__c", mismatch["field"])
        self.assertEqual("editable", mismatch["permission"])
        self.assertFalse(mismatch["expected"])
        self.assertTrue(mismatch["observed"])


if __name__ == "__main__":
    unittest.main()
