# Live Salesforce Release Evidence

> **Test what the Salesforce change means — not just whether it deploys.**

Salesforce Change Impact Lab has exercised three different Salesforce quality dimensions through real pull requests. Each dimension uses the same experimental pattern:

1. freeze the business intent before the change;
2. make a harmless governed change and require **GO**;
3. introduce one controlled semantic regression and require **NO-GO**;
4. preserve the negative-control PR unmerged as reviewable evidence.

The result is six live PR experiments across Validation Rules, Flows, and Permission Sets.

## Evidence matrix

| Requirement | Salesforce surface | Frozen business intent | Positive control | Negative control |
|---|---|---|---|---|
| `SF-OPP-001` | Opportunity Validation Rule | Discounts greater than 20% require Finance approval before Closed Won | [PR #13](https://github.com/bg-playground/salesforce-change-impact-lab/pull/13) — threshold remains `>20`; **GO**, merged | [PR #15](https://github.com/bg-playground/salesforce-change-impact-lab/pull/15) — threshold drifts `>20` → `>30`; **NO-GO**, closed unmerged |
| `SF-CASE-001` | Case record-triggered Flow | Strategic escalation requires High priority **AND** Strategic entitlement | [PR #21](https://github.com/bg-playground/salesforce-change-impact-lab/pull/21) — decision remains AND; **GO**, merged | [PR #23](https://github.com/bg-playground/salesforce-change-impact-lab/pull/23) — decision drifts AND → OR; **NO-GO**, closed unmerged |
| `SF-SEC-001` | Opportunity Permission Set | Sales reps may read Finance approval but must not edit it | [PR #27](https://github.com/bg-playground/salesforce-change-impact-lab/pull/27) — access remains read-only; **GO**, merged | [PR #28](https://github.com/bg-playground/salesforce-change-impact-lab/pull/28) — Finance approval becomes editable; **NO-GO**, closed unmerged |

The negative-control failures are successful test results. They show the release gate rejecting Salesforce metadata that no longer matches frozen business intent.

## What the lab adds

Conventional Salesforce quality checks answer important questions such as:

- Is the metadata structurally acceptable?
- Does static analysis identify known quality or security problems?
- Do Apex and LWC tests pass?
- Do selected runtime and UI journeys still work?

Change Impact Lab adds a separate question:

> **Does the changed implementation still mean what the business requirement says it must mean?**

That distinction matters because technical validity and business correctness are not the same property.

### Validation Rule proof

`SF-OPP-001` freezes a 20% discount boundary. Moving the implementation threshold to 30% does not merely change syntax: it creates a business interval in which discounts above the approved threshold can escape the Finance control. The independent oracle evaluates the contract and implementation around the boundary and returns NO-GO when they diverge.

### Flow proof

`SF-CASE-001` freezes a two-condition AND decision. Changing the Flow to OR remains a plausible Salesforce Flow configuration, but it changes which Cases qualify for escalation. A four-way truth table exposes the two combinations that the OR mutant incorrectly accepts.

### Permission Set proof

`SF-SEC-001` freezes a segregation-of-duties rule. Sales reps may maintain discount data and see Finance approval, but cannot edit the approval field themselves. Changing one field permission from `editable=false` to `editable=true` violates that access contract and receives NO-GO.

Together, the experiments show that the same intent-aware approach can reason about **numeric boundaries, boolean workflow logic, and least-privilege access semantics**.

## BGSTM evidence chain

The live experiment maps directly to the six BGSTM phases.

| BGSTM phase | Change Impact Lab evidence |
|---|---|
| **1. Test Planning** | Frozen `SF-OPP-001`, `SF-CASE-001`, and `SF-SEC-001` contracts define intent, risk, and the protected control before mutation. |
| **2. Test Case Development** | Boundary cases, Flow truth-table combinations, and field-access expectations are derived from the frozen contracts. |
| **3. Test Environment Preparation** | The deterministic reviewer path runs without Salesforce credentials; Salesforce DX metadata and CI provide the implementation context. |
| **4. Test Execution** | PR-aware change selection invokes the semantic oracle for the governed metadata type and executes conventional repository checks alongside it. |
| **5. Test Results Analysis** | Expected and observed semantics are compared, mismatches are counted, and the affected HIGH-risk business control is identified. |
| **6. Test Results Reporting** | PR job summaries, machine-readable evidence, CI status, and the final GO / NO-GO decision preserve a traceable release record. |

The requirement ID is the evidence spine. A changed Salesforce component is connected to a frozen requirement, selected evidence, observed semantics, mismatches, and a release decision.

## Release interpretation

A **GO** means the governed metadata examined by the semantic oracle remains aligned with its frozen contract. It does not mean the entire Salesforce release is automatically safe.

A **NO-GO** means a governed HIGH-risk control has demonstrably diverged from frozen business intent. That is sufficient for this lab's business-intent gate to reject the change even when other technical checks do not identify the semantic problem.

This is intentionally additive to Salesforce-native testing rather than a replacement for it.

## Why the negative PRs remain unmerged

PRs #15, #23, and #28 are controlled experimental artifacts. Merging them would deliberately place known business-rule regressions on `main`. Closing them unmerged preserves three useful properties:

- the exact mutation remains inspectable;
- the failed release-gate evidence remains associated with the change;
- `main` remains the known-good baseline for subsequent experiments.

## Scope and limitations

This repository demonstrates a pattern, not a universal Salesforce semantic engine.

- Each oracle intentionally supports a narrow, inspectable metadata pattern.
- Permission Set analysis covers explicit field permissions in the governed Permission Set; it does not calculate complete effective user access across profiles, Permission Set Groups, muting permission sets, assignments, and live org state.
- Offline evidence does not replace org-backed integration, authorization, or end-to-end testing where those layers are required.
- A GO decision is scoped to the controls and evidence actually evaluated.

The public path remains credential-free so reviewers can inspect and reproduce the core reasoning without access to a Salesforce org.

## Demonstrated result

Across three Salesforce mechanisms, the experiment produced the same pattern:

```text
harmless governed change  -> semantic alignment -> GO    -> merged
controlled intent drift   -> semantic mismatch  -> NO-GO -> closed unmerged
```

That is the central claim of Salesforce Change Impact Lab:

> **A Salesforce change can be technically valid and still be business-unsafe. Release evidence should evaluate both.**
