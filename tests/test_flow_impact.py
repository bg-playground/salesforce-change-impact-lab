import importlib.util,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("flow_impact",ROOT/"tools"/"flow_impact.py"); flow_impact=importlib.util.module_from_spec(spec); sys.modules[spec.name]=flow_impact; spec.loader.exec_module(flow_impact)
class FlowImpactTests(unittest.TestCase):
    contract=ROOT/"policies"/"SF-CASE-001.json"
    baseline=ROOT/"force-app"/"main"/"default"/"flows"/"Case_Strategic_Escalation.flow-meta.xml"
    mutant=ROOT/"mutations"/"Case_Strategic_Escalation.logic-or.flow-meta.xml"
    def test_baseline_is_go(self):
        r=flow_impact.analyze(self.baseline,self.contract); self.assertEqual("GO",r["release_decision"]); self.assertEqual(0,r["mismatch_count"]); self.assertEqual(4,r["case_count"])
    def test_or_mutation_is_no_go(self):
        r=flow_impact.analyze(self.mutant,self.contract); self.assertEqual("NO-GO",r["release_decision"]); self.assertEqual("or",r["observed_logic"]); self.assertEqual(2,r["mismatch_count"])
    def test_only_both_conditions_escalate_in_intent(self):
        r=flow_impact.analyze(self.baseline,self.contract); escalated=[c for c in r["cases"] if c["intent_should_escalate"]]; self.assertEqual(1,len(escalated))
if __name__=="__main__": unittest.main()
