# PR-aware change impact

The lab proves that Salesforce metadata can remain technically valid while drifting from frozen business intent. The PR-aware layer asks a second question:

> **Given this change, what deserves testing, and why?**

## Business-intent relevance

`impact/manifest.json` maps Salesforce components to governed business controls, risk, and the evidence selected when each control is touched.

This is deliberately complementary to platform/dependency-oriented test selection. A dependency graph can tell you that code or metadata is connected. The manifest adds a different dimension: which **business controls** are at risk, what evidence demonstrates them, and which tests are unnecessary for the change.

The current governed controls are:

- `SF-OPP-001` — Opportunity Validation Rule semantics
- `SF-CASE-001` — Case Flow decision semantics
- `SF-SEC-001` — Opportunity Permission Set access semantics

## Manual CLI path

The original single-control CLI remains supported:

```bash
python tools/pr_impact.py \
  --changed force-app/main/default/objects/Opportunity/validationRules/High_Discount_Requires_Finance.validationRule-meta.xml \
  --semantic-metadata mutations/High_Discount_Requires_Finance.threshold-30.validationRule-meta.xml \
  --json-out evidence/pr-impact-mutation.json
```

For multi-control evaluation, repeat `--semantic-control` with the requirement ID, semantic kind, metadata path, and frozen contract:

```bash
python tools/pr_impact.py \
  --changed \
    force-app/main/default/objects/Opportunity/validationRules/High_Discount_Requires_Finance.validationRule-meta.xml \
    force-app/main/default/flows/Case_Strategic_Escalation.flow-meta.xml \
  --semantic-control \
    SF-OPP-001 validation-rule \
    force-app/main/default/objects/Opportunity/validationRules/High_Discount_Requires_Finance.validationRule-meta.xml \
    policies/SF-OPP-001.json \
  --semantic-control \
    SF-CASE-001 flow \
    force-app/main/default/flows/Case_Strategic_Escalation.flow-meta.xml \
    policies/SF-CASE-001.json
```

Semantic evidence is stored by requirement ID rather than as one global result:

```json
{
  "semantic_evidence": {
    "SF-OPP-001": {
      "release_decision": "GO"
    },
    "SF-CASE-001": {
      "release_decision": "GO"
    }
  }
}
```

## GitHub pull-request path

`.github/workflows/pr-impact.yml` derives the changed files from the PR and can now invoke **all** relevant semantic oracles in the same run.

For every pull request it:

1. checks out the PR with enough history to compare base and head commits;
2. derives `changed-files.txt` directly from the pull request diff;
3. identifies every governed semantic metadata component that changed;
4. supplies one `--semantic-control` entry for each applicable Validation Rule, Flow, and Permission Set control;
5. runs one aggregate PR-impact decision;
6. writes the readable per-control evidence and aggregate decision to the GitHub Actions job summary;
7. uploads the changed-file list plus JSON and text evidence as workflow artifacts; and
8. fails the job when **any** impacted semantic control returns `NO-GO`.

No Salesforce org credentials are required for this proof. The release decision continues to come from frozen intent and repository metadata rather than from the implementation claiming that it is correct.

## Aggregate decision rules

The aggregation is deliberately conservative and deterministic:

- `NO-IMPACT` — no changed file maps to a frozen business control.
- `NO-GO` — at least one impacted control has semantic evidence with `NO-GO`. A known business-intent failure takes precedence even if another impacted control still lacks evidence.
- `REVIEW` — one or more controls are impacted but required semantic evidence is still missing, and no supplied semantic result is `NO-GO`.
- `GO` — every impacted control has semantic evidence and every supplied semantic result is `GO`.

This prevents a passing control from masking a failing one and prevents a partially evaluated multi-control PR from receiving GO.

Representative multi-control output:

```text
PR IMPACT

Affected business controls:
  SF-OPP-001  HIGH RISK
  SF-CASE-001 HIGH RISK

Semantic evidence:
  SF-CASE-001:
    contract logic: AND
    metadata logic: OR
    conditions aligned: True
    mismatches: 2
    decision: NO-GO
  SF-OPP-001:
    contract threshold: >20%
    metadata threshold: >20%
    mismatches: 0
    decision: GO

Decision: NO-GO
Reason: Business-intent drift detected in: SF-CASE-001.
```

## Why aggregation matters

Real Salesforce pull requests do not necessarily respect test-tool boundaries. A single change set can alter an Opportunity Validation Rule, a Flow, and a Permission Set together. First-match routing would under-report that risk by evaluating only one semantic control.

The aggregate model keeps each requirement independently traceable while producing one release-level decision:

```text
changed files
    │
    ├── SF-OPP-001 ── semantic evidence ── GO
    ├── SF-CASE-001 ─ semantic evidence ── NO-GO
    └── SF-SEC-001 ── semantic evidence ── GO
                           │
                           ▼
                    aggregate NO-GO
```

## Deliberate limitations

The manifest remains intentionally explicit rather than magical. This increment does not claim to infer every Salesforce dependency, parse every metadata type, or auto-discover every business requirement. Its value is explainability: reviewers can inspect why each control was selected and how its evidence contributed to the final release decision.

The workflow continues to publish to the job summary rather than creating a new PR comment on every synchronization event. That avoids notification noise while making the decision visible in the required check.

Future increments can add BGSTM External Results aggregation, metadata/dependency graphs, org-backed runtime evidence, and targeted browser evidence without changing the per-requirement aggregation model.
