# Salesforce Flow semantic validation

`SF-CASE-001` is the lab's second governed business control and deliberately exercises a different semantic failure mode from `SF-OPP-001`.

## Frozen intent

A Case qualifies for strategic escalation only when both conditions are true:

1. `Priority = High`
2. `Entitlement_Level__c = Strategic`

The baseline `Case_Strategic_Escalation` Flow represents this with a decision rule whose `conditionLogic` is `and`.

## Controlled drift

`mutations/Case_Strategic_Escalation.logic-or.flow-meta.xml` changes only the decision semantics from `AND` to `OR`. That broadens the rule so either condition can trigger escalation.

The independent oracle in `tools/flow_impact.py` extracts the named decision/rule, compares the boolean logic and conditions with the frozen contract, and evaluates all four combinations of Priority and Entitlement Level. The baseline must produce zero mismatches and **GO**; the mutation must expose two mismatches and produce **NO-GO**.

## Why this matters

Salesforce Flow is metadata-driven application logic. Structurally plausible XML, successful deployment, and unrelated tests do not by themselves prove that a branch still represents the intended business policy. This check adds semantic evidence at the business-control boundary.

This is intentionally a narrow, inspectable proof—not a general Flow parser. It supports the named decision-rule pattern used by this lab. Production use would require broader Flow-node coverage, schema/version validation, org-backed Flow tests, and stronger dependency analysis.
