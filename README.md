# Salesforce Change Impact Lab

> **Test what the Salesforce change means — not just whether it deploys.**

Salesforce Change Impact Lab is a compact testing demo combining Salesforce DX conventions with ideas from [BGSTM](https://github.com/bg-playground/BGSTM), NAT-style intent validation, and Agent Crash Lab's evidence-first evaluation approach.

A deliberately subtle Salesforce regression is included:

- Business intent: Opportunities with a discount **greater than 20%** require Finance approval before `Closed Won`.
- Baseline metadata enforces `> 20`.
- Mutated metadata silently drifts to `> 30`.
- A normal low-discount happy-path test can still pass.
- The lab independently compares Salesforce metadata to a frozen business-intent contract and exercises boundary cases.
- The baseline receives **GO**.
- The mutant receives **NO-GO**, with machine-readable and HTML evidence.

The core demo runs offline in seconds and does **not** require Salesforce credentials.

## Why this is different

Typical Salesforce quality pipelines ask whether metadata deploys, Apex/LWC tests pass, code coverage is sufficient, and selected UI journeys still work. Those checks are necessary, but can miss a different failure mode:

> **The implementation is valid Salesforce, the tests are green, but the business rule itself drifted.**

This lab adds a compact intent-aware layer:

```text
Frozen business intent
        │
        ▼
Salesforce metadata ──► semantic extraction
        │                    │
        │                    ▼
        │              independent oracle
        │                    │
        ├──────────────► boundary cases
        │                    │
        ▼                    ▼
standard SF checks      evidence + decision
(Code Analyzer,         GO / NO-GO
 Apex, LWC, E2E)
```

## 60-second demo

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

The mutation command intentionally exits non-zero. The committed unit test verifies that this failure is detected.

## Run the tests

```bash
python -m unittest discover -s tests -v
```

No third-party Python packages are required.

## Salesforce best-practice layers

This demo is intentionally additive rather than a replacement for native Salesforce testing:

- **Salesforce DX project structure** is used for metadata.
- **Apex tests** are included for the server-side guard example.
- **LWC Jest** is the recommended unit-test layer when the demo is extended with Lightning Web Components.
- **Salesforce Code Analyzer v5** is represented in CI as the static-analysis layer.
- **End-to-end UI automation** belongs at the top of the pyramid, not as a substitute for unit and metadata-level checks.
- The core intent proof remains offline and deterministic so reviewers can reproduce it without an org.

## BGSTM mapping

| BGSTM phase | Lab artifact |
|---|---|
| 1. Test Planning | `policies/SF-OPP-001.json` freezes business intent and risk |
| 2. Test Case Development | Boundary cases are generated from the contract |
| 3. Environment Preparation | Offline core + optional scratch-org config |
| 4. Test Execution | Metadata extraction + independent oracle evaluation |
| 5. Results Analysis | Semantic drift and affected cases are calculated |
| 6. Results Reporting | JSON + deterministic HTML release evidence |

The requirement ID (`SF-OPP-001`) is carried through the contract and reports, making the evidence chain explicit.

## Repository map

```text
force-app/       Salesforce DX metadata + Apex example
policies/        Frozen business-intent contracts
mutations/       Deliberate semantic regressions
tools/           Deterministic intent/evidence runner
tests/           Offline regression tests for the lab itself
evidence/        Generated baseline and mutation reports
config/          Scratch-org definition
.github/         CI examples
docs/            Architecture and extension notes
```

## Optional real-org extension

The offline lab is the reviewer-friendly proof. A real project can layer on scratch-org creation, metadata deployment, Apex tests, LWC Jest tests, Salesforce Code Analyzer, targeted Playwright/UTAM E2E checks, BGSTM external-results reporting, and NAT-managed execution at scale.

The key idea stays the same: **use changed Salesforce metadata plus frozen intent to decide what deserves deeper testing and to explain the release risk.**

## Safety and scope

This is a demonstration project. The semantic extractor intentionally supports one narrow validation-rule pattern so that the proof is easy to inspect. It should not be treated as a general Salesforce formula parser or production release gate without further hardening.

## License

MIT.
