import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("impact_lab", ROOT / "tools" / "impact_lab.py")
impact_lab = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = impact_lab
SPEC.loader.exec_module(impact_lab)

class ImpactLabTests(unittest.TestCase):
    def setUp(self):
        self.contract = ROOT / "policies" / "SF-OPP-001.json"
        self.baseline = ROOT / "tests" / "fixtures" / "baseline" / "High_Discount_Requires_Finance.validationRule-meta.xml"
        self.mutant = ROOT / "mutations" / "High_Discount_Requires_Finance.threshold-30.validationRule-meta.xml"

    def test_baseline_is_go(self):
        report = impact_lab.analyze(self.baseline, self.contract)
        self.assertEqual("GO", report["release_decision"])
        self.assertEqual(20, report["observed_threshold"])
        self.assertEqual(0, report["mismatch_count"])

    def test_threshold_drift_is_no_go(self):
        report = impact_lab.analyze(self.mutant, self.contract)
        self.assertEqual("NO-GO", report["release_decision"])
        self.assertEqual(30, report["observed_threshold"])
        self.assertGreater(report["mismatch_count"], 0)

    def test_boundary_above_twenty_exposes_mutant(self):
        report = impact_lab.analyze(self.mutant, self.contract)
        exposed = [c for c in report["cases"] if c["discount"] == 20.01 and not c["matches_intent"]]
        self.assertEqual(1, len(exposed))
        self.assertTrue(exposed[0]["intent_should_block"])
        self.assertFalse(exposed[0]["metadata_would_block"])

if __name__ == "__main__": unittest.main()
