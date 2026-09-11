# Permission Set semantic validation

`SF-SEC-001` extends Change Impact Lab from business-rule semantics into Salesforce access semantics.

## Frozen intent

The governed `Sales_Rep_Opportunity_Access` Permission Set supports sales work without allowing self-approval:

- `Opportunity.Discount_Percent__c`: readable and editable.
- `Opportunity.Finance_Approved__c`: readable but **not editable**.

This is a narrow segregation-of-duties example. The purpose is not to infer every effective permission in an org; it is to prove that a reviewed access contract can be compared deterministically with Permission Set metadata before release.

## Controlled drift

The mutation fixture changes only `Opportunity.Finance_Approved__c` from `editable=false` to `editable=true`. The XML can remain structurally valid while violating least-privilege intent.

Expected evidence:

```text
SF-SEC-001: GO | Finance_Approved__c editable=False | mismatches=0
SF-SEC-001: NO-GO | Finance_Approved__c editable=True | mismatches=1
```

## PR-native behavior

When the governed Permission Set changes, `.github/workflows/pr-impact.yml` selects `SF-SEC-001`, runs `tools/permission_impact.py`, publishes reviewer-facing evidence, and fails the PR check on `NO-GO`.

The deterministic public-review path needs no Salesforce org credentials. An org-backed User Access Summary review remains recommended because effective access can also be influenced by assignments, Permission Set Groups, muting, profiles, and other org configuration.

## Deliberate limitations

The current oracle intentionally supports explicit field permissions in one Permission Set. It does not claim to calculate a user's complete effective Salesforce authorization graph. Future expansion can add Permission Set Groups, muting permission sets, object permissions, custom permissions, and org-backed effective-access evidence while retaining the same frozen-contract and evidence model.
