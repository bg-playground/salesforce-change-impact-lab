#!/usr/bin/env python3
"""Deterministic Salesforce intent-vs-metadata evidence runner."""
from __future__ import annotations
import argparse, json, re, sys
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from html import escape
from pathlib import Path
import xml.etree.ElementTree as ET

@dataclass(frozen=True)
class Case:
    discount: float
    finance_approved: bool
    stage: str

def load_contract(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))

def extract_formula_and_message(path: Path) -> tuple[str, str]:
    root = ET.parse(path).getroot()
    ns = {"sf": "http://soap.sforce.com/2006/04/metadata"}
    formula = root.findtext("sf:errorConditionFormula", default="", namespaces=ns)
    message = root.findtext("sf:errorMessage", default="", namespaces=ns)
    if not formula:
        raise ValueError("No errorConditionFormula found")
    return formula, message

def extract_threshold(formula: str, field: str) -> float:
    match = re.search(rf"\b{re.escape(field)}\s*>\s*(\d+(?:\.\d+)?)", formula)
    if not match:
        raise ValueError(f"Could not extract a '>' threshold for {field}")
    return float(match.group(1))

def intended_blocks(case: Case, contract: dict) -> bool:
    return case.stage == contract["stage"] and case.discount > float(contract["threshold"]) and not case.finance_approved

def implementation_blocks(case: Case, observed_threshold: float, contract: dict) -> bool:
    return case.stage == contract["stage"] and case.discount > observed_threshold and not case.finance_approved

def boundary_cases(contract: dict) -> list[Case]:
    t = float(contract["threshold"])
    return [Case(t-.01,False,contract["stage"]), Case(t,False,contract["stage"]), Case(t+.01,False,contract["stage"]), Case(t+5,False,contract["stage"]), Case(t+15,False,contract["stage"]), Case(t+15,True,contract["stage"]), Case(t+15,False,"Proposal/Price Quote")]

def analyze(metadata: Path, contract_path: Path) -> dict:
    contract = load_contract(contract_path)
    formula, message = extract_formula_and_message(metadata)
    observed = extract_threshold(formula, contract["discount_field"])
    expected = float(contract["threshold"])
    rows=[]; mismatches=0
    for case in boundary_cases(contract):
        intended=intended_blocks(case,contract); actual=implementation_blocks(case,observed,contract); matches=intended==actual
        mismatches += int(not matches)
        rows.append({**asdict(case),"intent_should_block":intended,"metadata_would_block":actual,"matches_intent":matches})
    decision="GO" if observed==expected and mismatches==0 else "NO-GO"
    return {"schema_version":"1.0","generated_at":datetime.now(timezone.utc).isoformat(),"requirement_id":contract["requirement_id"],"title":contract["title"],"risk":contract["risk"],"metadata_path":str(metadata).replace("\\","/"),"contract_path":str(contract_path).replace("\\","/"),"expected_threshold":expected,"observed_threshold":observed,"threshold_aligned":observed==expected,"error_message_mentions_expected_threshold":str(int(expected)) in message,"formula":formula,"case_count":len(rows),"mismatch_count":mismatches,"cases":rows,"release_decision":decision,"decision_reason":"Salesforce metadata matches the frozen business intent and all generated boundary cases." if decision=="GO" else "Salesforce metadata diverges from frozen business intent; at least one business boundary is under-protected.","bgstm_trace":{"phase_1_planning":contract["bgstm"]["planning_risk"],"phase_2_test_design":"Generated boundary cases from frozen intent","phase_4_execution":"Independent metadata oracle","phase_5_analysis":f"{mismatches} semantic case mismatch(es)","phase_6_reporting":decision,"traceability_id":contract["bgstm"]["traceability_id"]}}

def render_html(r: dict) -> str:
    rows="".join(f"<tr><td>{c['discount']:.2f}%</td><td>{escape(c['stage'])}</td><td>{'yes' if c['finance_approved'] else 'no'}</td><td>{'BLOCK' if c['intent_should_block'] else 'allow'}</td><td>{'BLOCK' if c['metadata_would_block'] else 'allow'}</td><td>{'✓' if c['matches_intent'] else '✕'}</td></tr>" for c in r["cases"])
    cls="go" if r["release_decision"]=="GO" else "nogo"
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(r['requirement_id'])} — Salesforce Change Impact Lab</title><style>:root{{font-family:Inter,system-ui,sans-serif;color:#172033;background:#f6f8fb}}main{{max-width:1050px;margin:auto;padding:40px 24px}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:14px}}.card{{background:white;border:1px solid #dfe5ec;border-radius:14px;padding:18px;margin-top:20px}}.value{{font-size:28px;font-weight:750}}.go .value{{color:#2e844a}}.nogo .value{{color:#ba0517}}table{{width:100%;border-collapse:collapse;background:white}}th,td{{padding:12px;border-bottom:1px solid #edf0f4;text-align:left}}th{{background:#eef3f8}}pre{{white-space:pre-wrap;background:#101828;color:#eef4ff;padding:18px;border-radius:14px}}</style></head><body><main><p>Salesforce Change Impact Lab · {escape(r['requirement_id'])}</p><h1>{escape(r['title'])}</h1><div class="grid"><div class="card {cls}"><small>Release decision</small><div class="value">{r['release_decision']}</div></div><div class="card"><small>Contract threshold</small><div class="value">{r['expected_threshold']:.0f}%</div></div><div class="card"><small>Metadata threshold</small><div class="value">{r['observed_threshold']:.0f}%</div></div><div class="card"><small>Semantic mismatches</small><div class="value">{r['mismatch_count']}</div></div></div><div class="card"><h2>Decision rationale</h2><p>{escape(r['decision_reason'])}</p></div><h2>Boundary evidence</h2><table><thead><tr><th>Discount</th><th>Stage</th><th>Finance approved</th><th>Intent</th><th>Metadata</th><th>Match</th></tr></thead><tbody>{rows}</tbody></table><h2>Extracted Salesforce formula</h2><pre>{escape(r['formula'])}</pre></main></body></html>'''

def main() -> int:
    p=argparse.ArgumentParser(); p.add_argument("--metadata",required=True,type=Path); p.add_argument("--contract",required=True,type=Path); p.add_argument("--json-out",type=Path); p.add_argument("--html-out",type=Path); a=p.parse_args()
    r=analyze(a.metadata,a.contract)
    if a.json_out: a.json_out.parent.mkdir(parents=True,exist_ok=True); a.json_out.write_text(json.dumps(r,indent=2)+"\n",encoding="utf-8")
    if a.html_out: a.html_out.parent.mkdir(parents=True,exist_ok=True); a.html_out.write_text(render_html(r),encoding="utf-8")
    print(f"{r['requirement_id']}: {r['release_decision']} | contract>{r['expected_threshold']:.0f}% metadata>{r['observed_threshold']:.0f}% | mismatches={r['mismatch_count']}")
    return 0 if r["release_decision"]=="GO" else 2
if __name__=="__main__": sys.exit(main())
