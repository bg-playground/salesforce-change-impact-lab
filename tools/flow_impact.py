#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,sys
from itertools import product
from pathlib import Path
import xml.etree.ElementTree as ET
NS={"sf":"http://soap.sforce.com/2006/04/metadata"}

def load_json(p): return json.loads(Path(p).read_text(encoding="utf-8"))
def extract(flow_path, contract):
    root=ET.parse(flow_path).getroot()
    decision=next((d for d in root.findall("sf:decisions",NS) if d.findtext("sf:name",namespaces=NS)==contract["decision_name"]),None)
    if decision is None: raise ValueError("Decision node not found")
    rule=next((r for r in decision.findall("sf:rules",NS) if r.findtext("sf:name",namespaces=NS)==contract["rule_name"]),None)
    if rule is None: raise ValueError("Decision rule not found")
    logic=(rule.findtext("sf:conditionLogic",default="",namespaces=NS) or "").lower()
    conditions=[]
    for c in rule.findall("sf:conditions",NS):
        rv=c.find("sf:rightValue",NS)
        val=""
        if rv is not None:
            val=rv.findtext("sf:stringValue",default="",namespaces=NS)
        conditions.append({"field":c.findtext("sf:leftValueReference",default="",namespaces=NS),"operator":c.findtext("sf:operator",default="",namespaces=NS),"value":val})
    return logic,conditions

def evaluate(case, conditions, logic):
    checks=[]
    for c in conditions:
        observed=case[c["field"]]
        checks.append(observed==c["value"] if c["operator"]=="EqualTo" else False)
    return all(checks) if logic=="and" else any(checks) if logic=="or" else False

def analyze(flow_path, contract_path):
    contract=load_json(contract_path); logic,conditions=extract(flow_path,contract)
    values=[[c["value"], "Low" if c["field"]=="$Record.Priority" else "Standard"] for c in contract["conditions"]]
    rows=[]; mismatches=0
    for combo in product(*values):
        case={contract["conditions"][i]["field"]:combo[i] for i in range(len(combo))}
        intended=evaluate(case,contract["conditions"],contract["logic"]); actual=evaluate(case,conditions,logic); match=intended==actual; mismatches+=int(not match)
        rows.append({"inputs":case,"intent_should_escalate":intended,"flow_would_escalate":actual,"matches_intent":match})
    conditions_aligned=conditions==contract["conditions"]
    decision="GO" if logic==contract["logic"] and conditions_aligned and mismatches==0 else "NO-GO"
    return {"schema_version":"1.0","requirement_id":contract["requirement_id"],"risk":contract["risk"],"expected_logic":contract["logic"],"observed_logic":logic,"conditions_aligned":conditions_aligned,"mismatch_count":mismatches,"case_count":len(rows),"cases":rows,"release_decision":decision,"decision_reason":"Flow decision semantics match frozen business intent." if decision=="GO" else "Flow decision semantics diverge from frozen business intent."}

def main():
    p=argparse.ArgumentParser();p.add_argument("--flow",required=True,type=Path);p.add_argument("--contract",required=True,type=Path);p.add_argument("--json-out",type=Path);a=p.parse_args();r=analyze(a.flow,a.contract)
    if a.json_out:a.json_out.parent.mkdir(parents=True,exist_ok=True);a.json_out.write_text(json.dumps(r,indent=2)+"\n",encoding="utf-8")
    print(f"{r['requirement_id']}: {r['release_decision']} | contract={r['expected_logic'].upper()} flow={r['observed_logic'].upper()} | mismatches={r['mismatch_count']}")
    return 0 if r["release_decision"]=="GO" else 2
if __name__=="__main__":sys.exit(main())
