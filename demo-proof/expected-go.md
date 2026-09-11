# Expected reviewer-facing evidence

```text
PR IMPACT

Affected business controls:
  SF-OPP-001  HIGH RISK

Selected evidence:
  ✓ semantic contract check
  ✓ threshold boundary cases
  ✓ Apex OpportunityReleaseGuardTest
  → Playwright OPP-07 recommended

Semantic evidence:
  contract threshold: >20%
  metadata threshold: >20%
  mismatches: 0

Decision: GO
```

The important proof is not that CI is green in general. It is that a real Salesforce metadata change is recognized as business-relevant, the appropriate evidence is selected, and the implementation is independently verified against frozen intent.
