# PR-aware change impact

The initial lab proves that Salesforce metadata can remain valid while drifting from frozen business intent. The PR-aware layer adds the next question:

> **Given this change, what deserves testing, and why?**

## Business-intent relevance

`impact/manifest.json` maps Salesforce components to a business control (`SF-OPP-001`), its risk, and the evidence that should be selected when that control is touched.

This is deliberately complementary to platform/dependency-oriented test selection. A dependency graph can tell you that code or metadata is connected. The manifest adds a different dimension: which **business control** is at risk, what evidence demonstrates that control, and which tests are unnecessary for this change.

## Example

```bash
python tools/pr_impact.py \
  --changed force-app/main/default/objects/Opportunity/validationRules/High_Discount_Requires_Finance.validationRule-meta.xml \
  --semantic-metadata mutations/High_Discount_Requires_Finance.threshold-30.validationRule-meta.xml \
  --json-out evidence/pr-impact-mutation.json
```

The command intentionally exits `2` because the changed component maps to a high-risk business control and the supplied metadata weakens its threshold from `>20%` to `>30%`.

Representative output:

```text
PR IMPACT

Affected business controls:
  SF-OPP-001  HIGH RISK

    selected evidence:
      ✓ semantic contract check
      ✓ threshold boundary cases
      ✓ Apex OpportunityReleaseGuardTest
      → Playwright OPP-07

    not selected:
      - Permission-set regression — No permission metadata participates in SF-OPP-001.

Semantic evidence:
  contract threshold: >20%
  metadata threshold: >30%
  mismatches: 2

Decision: NO-GO
```

## Decision states

- `NO-IMPACT`: no changed file maps to a frozen control in the current manifest.
- `REVIEW`: a business control is affected but semantic evidence was not supplied yet.
- `GO`: an affected control was evaluated and its implementation matches frozen intent.
- `NO-GO`: an affected control was evaluated and semantic evidence found drift.

## Deliberate limitations

The manifest is intentionally explicit rather than magical. This increment does not claim to infer every Salesforce dependency, parse every metadata type, or auto-discover every business requirement. Its value is explainability: a reviewer can inspect exactly why evidence was selected and exactly why other evidence was skipped.

Future increments can replace portions of the explicit manifest with metadata graphs, Flow analysis, Apex dependencies, permission relationships, and BGSTM external-results aggregation without changing the decision model.
