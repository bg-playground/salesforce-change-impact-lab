# BGSTM and related-project mapping

This demo intentionally reuses ideas rather than copying whole products.

## BGSTM

BGSTM contributes the six-phase lifecycle, risk awareness, traceability, and evidence-based release decision. The frozen `SF-OPP-001` contract is the thread connecting planning, test generation, execution, analysis, and reporting.

## bgstm-playwright-frameworks

The existing CRM pack already identifies Salesforce-like domain entities such as Leads, Opportunities, and Accounts and supports BGSTM requirement annotations. A future E2E extension should use the same requirement ID in the Playwright annotation so browser evidence and semantic evidence converge on the same traceability key.

## NAT / AegisFlow

AegisFlow's transferable idea is semantic validation: compare implementation logic to written business intent, then produce executable evidence. This demo applies that concept to Salesforce metadata rather than SQL/dbt transformations.

## Agent Crash Lab

Crash Lab contributes experimental discipline: freeze the rule before running the experiment, inject a controlled mutation, use an independent oracle, retain machine-readable evidence, and do not hide an inconvenient failure behind a successful demo.

The `>30` mutation is therefore not an accidental defect. It is a controlled proof that the quality gate can detect a meaningful semantic regression.
