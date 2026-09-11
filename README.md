# Salesforce Change Impact Lab

> **Test what the Salesforce change means — not just whether it deploys.**

Salesforce Change Impact Lab is a compact testing demo combining Salesforce DX conventions with ideas from [BGSTM](https://github.com/bg-playground/BGSTM), NAT-style intent validation, and Agent Crash Lab's evidence-first evaluation approach.

The lab freezes HIGH-risk business intent, detects which governed Salesforce metadata changed, compares implementation semantics to that intent, and produces an explainable **GO / NO-GO** release decision. The core reviewer path runs offline in seconds and does **not** require Salesforce credentials.

## Live PR-native proof

Three Salesforce quality dimensions have now been exercised through paired live pull requests. In every pair, a harmless governed change receives **GO** and merges; a controlled business-intent regression receives **NO-GO** and is preserved closed and unmerged.

| Requirement | Salesforce surface | GO proof | NO-GO proof |
|---|---|---|---|
| `SF-OPP-001` | Opportunity Validation Rule | [PR #13](https://github.com/bg-playground/salesforce-change-impact-lab/pull/13) — preserved `>20%` approval boundary; **merged** | [PR #15](https://github.com/bg-playground/salesforce-change-impact-lab/pull/15) — drifted `>20%` → `>30%`; **closed unmerged** |
| `SF-CASE-001` | Case Flow decision | [PR #21](https://github.com/bg-playground/salesforce-change-impact-lab/pull/21) — preserved AND semantics; **merged** | [PR #23](https://github.com/bg-playground/salesforce-change-impact-lab/pull/23) — drifted AND → OR; **closed unmerged** |
| `SF-SEC-001` | Opportunity Permission Set | [PR #27](https://github.com/bg-playground/salesforce-change-impact-lab/pull/27) — preserved Finance read-only access; **merged** | [PR #28](https://github.com/bg-playground/salesforce-change-impact-lab/pull/28) — granted Finance edit access; **closed unmerged** |

The red CI on the negative-control PRs is the successful test result, not unresolved build debt. The gate rejected governed Salesforce changes because their implemented meaning no longer matched frozen business intent.

**Numeric boundary. Boolean workflow logic. Least-privilege access. Same evidence-first release pattern.**

See [Live Salesforce Release Evidence](docs/LIVE_RELEASE_EVIDENCE.md) for the full six-PR experiment, BGSTM evidence chain, release interpretation, and explicit limitations.

### Isolated multi-control release signal

[PR #38](https://github.com/bg-playground/salesforce-change-impact-lab/pull/38) then exercised two governed controls in one release candidate after the oracle fixtures were isolated from live metadata:

```text
Demo CI                    GREEN
Salesforce Code Analyzer   GREEN
PR Change Impact           RED / NO-GO

SF-OPP-001                 GO      (0 mismatches)
SF-CASE-001                NO-GO   (2 mismatches)
Aggregate release          NO-GO
```

That result is the core thesis in one PR: healthy test machinery and structurally valid Salesforce metadata can coexist with a business-unsafe release candidate.

## BGSTM-compatible release evidence

`tools/bgstm_release_evidence.py` turns requirement-aware PR impact evidence plus normalized supporting signals into one deterministic release bundle aligned with BGSTM External Results v1. It emits a session request, requirement-linked case-result templates, a finish-session request, and one release decision without making network calls or requiring secrets.

Passing static analysis or runtime evidence can never mask a semantic `NO-GO`. Missing required evidence produces `REVIEW`; any failed required signal produces `NO-GO`; all required supplied evidence must pass for `GO`.

See [BGSTM-compatible Release Evidence](docs/BGSTM_RELEASE_EVIDENCE.md) for the CLI, bundle shape, upload sequence, and future Playwright/runtime integration path.

## Why this is different

Typical Salesforce quality pipelines ask whether metadata is valid, static analysis passes, Apex/LWC tests succeed, and selected runtime or UI journeys still work. Those checks are necessary, but they can miss a different failure mode:

> **The implementation is valid Salesforce, but the business control itself drifted.**

This lab adds a compact intent-aware layer:

```text
Changed Salesforce metadata
          │
          ▼
 PR-aware impact selection ─────► governed requirement + risk
          │                              │
          ▼                              ▼
 semantic extraction ───────────► frozen business intent
          │                              │
          └──────────────┬───────────────┘
                         ▼
                  independent oracle
                         │
                         ▼
             evidence + GO / NO-GO
```

Conventional Salesforce checks remain part of the quality stack. Change Impact Lab adds the question: **does the changed implementation still mean what the protected business requirement says it must mean?**

## Three governed controls

### `SF-OPP-001` — Validation Rule boundary

Business intent: Opportunities with a discount **greater than 20%** require Finance approval before `Closed Won`.

- Baseline metadata enforces `>20`.
- Controlled mutant drifts to `>30`.
- Boundary evaluation exposes the semantic gap.

### `SF-CASE-001` — Flow decision logic

Business intent: strategic Case escalation requires **High priority AND Strategic entitlement**.

- Baseline Flow uses AND.
- Controlled mutant changes the decision to OR.
- A four-way truth table exposes two incorrect outcomes.

### `SF-SEC-001` — Permission Set segregation of duties

Business intent: sales reps may maintain Opportunity discounts and read Finance approval, but **must not edit Finance approval**.

- Baseline Permission Set has `Finance_Approved__c editable=false`.
- Controlled mutant changes that single permission to `editable=true`.
- The access contract records one mismatch and returns NO-GO.

## 60-second Validation Rule demo

```bash
python tools/impact_lab.py \
  --metadata force-app/main/default/objects/Opportunity/validationRules/High_Discount_Requires_Finance.validationRule-meta.xml \
  --contract policies/SF-OPP-001.json \
  --json-out evidence/baseline-report.json \
  --html-out evidence/baseline-report.html

python tools/impact_lab.py \
  --metadata mutations/High_Discount_Requires_Finance.threshold-30.validationRule-meta.xml \
  --contract policies/SF-OPP-001.json \
  --json-out evidence/mutation-report.json \
  --html-out evidence/mutation-report.html
```

Expected result:

| Scenario | Observed threshold | Contract threshold | Decision |
|---|---:|---:|---|
| Baseline | 20% | 20% | **GO** |
| Mutant | 30% | 20% | **NO-GO** |

The mutation command intentionally exits non-zero. The committed tests verify that the regression is detected.

## Run the tests

```bash
python -m unittest discover -s tests -v
```

No third-party Python packages are required.

## Salesforce best-practice layers

This demo is intentionally additive rather than a replacement for native Salesforce testing:

- **Salesforce DX project structure** is used for metadata.
- **Apex tests** are included for the server-side guard example.
- **LWC Jest** belongs at the Lightning Web Component unit-test layer when UI components are added.
- **Salesforce Code Analyzer** remains a static-analysis layer in CI.
- **Flow/runtime and end-to-end UI tests** provide execution evidence where appropriate.
- **Change Impact Lab** adds PR-aware, business-intent semantic evidence and release reasoning.
- The core proof remains offline and deterministic so public reviewers can reproduce it without an org.

## BGSTM mapping

| BGSTM phase | Lab artifact |
|---|---|
| 1. Test Planning | Frozen `SF-OPP-001`, `SF-CASE-001`, and `SF-SEC-001` contracts define intent and risk |
| 2. Test Case Development | Boundary cases, truth-table cases, and access expectations are derived from contracts |
| 3. Environment Preparation | Credential-free offline core + Salesforce DX metadata + optional org-backed layers |
| 4. Test Execution | PR-aware selection invokes the relevant semantic oracle alongside conventional checks |
| 5. Results Analysis | Expected vs observed semantics, mismatches, and affected HIGH-risk controls are calculated |
| 6. Results Reporting | PR summaries, machine-readable evidence, CI status, GO / NO-GO, and BGSTM-compatible release bundles preserve the release record |

The requirement ID is carried from frozen intent through impact selection and evidence, making the release-decision chain explicit.

## Repository map

```text
force-app/       Salesforce DX metadata + Apex examples
policies/        Frozen business-intent contracts
mutations/       Deliberate semantic regressions
tools/           Deterministic semantic, PR-impact, and release-evidence runners
tests/           Offline regression tests for the lab itself
evidence/        Generated evidence artifacts
config/          Scratch-org definition
.github/         CI and PR-native impact workflows
docs/            Architecture, semantic-control, and live-evidence notes
```

## Optional real-org extension

The offline lab is the reviewer-friendly proof. A real project can layer on scratch-org creation, metadata deployment, Apex tests, LWC Jest tests, Salesforce Code Analyzer, Flow/runtime tests, targeted Playwright/UTAM E2E checks, BGSTM external-results reporting, and NAT-managed execution at scale.

The key idea stays the same: **use changed Salesforce metadata plus frozen intent to decide what deserves deeper testing and to explain the release risk.**

## Safety and scope

This is a demonstration project, not a universal Salesforce semantic engine. Each extractor intentionally supports a narrow, inspectable metadata pattern. Permission analysis does not claim to calculate complete effective access across profiles, Permission Set Groups, muting permission sets, assignments, and live org state. A GO decision is scoped to the controls and evidence actually evaluated.

## License

MIT.
