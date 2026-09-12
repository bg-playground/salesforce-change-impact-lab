# BGSTM-compatible release evidence

Salesforce Change Impact Lab rolls requirement-aware semantic evidence together with supporting release signals into a deterministic handoff bundle aligned with BGSTM External Results v1. The offline adapter itself makes no BGSTM network calls. Real Salesforce runtime evidence is optional and is supplied only by the authenticated GitHub Actions workflow described below.

## Decision precedence

```text
business-intent NO-GO              -> NO-GO
required supporting signal failed  -> NO-GO
required evidence missing/rejected -> REVIEW
all required supplied evidence OK  -> GO
```

A passing Code Analyzer or Apex/runtime signal can never override a semantic `NO-GO`.

## SHA-bound supporting evidence

Both release-wide supporting signals use the same evidence contract:

```json
{
  "schema": "salesforce-change-impact-lab.supporting-evidence.v1",
  "source": "salesforce-apex-runtime",
  "status": "passed",
  "git_sha": "abc123",
  "run_id": "123",
  "run_url": "https://github.com/example/repo/actions/runs/123",
  "summary": {}
}
```

The release aggregator validates schema, source, status, and the expected Git SHA. Missing, malformed, wrong-source, or SHA-mismatched evidence is normalized to `not-run`, producing `REVIEW` unless a stronger `NO-GO` already exists.

### Salesforce Code Analyzer

The Code Analyzer workflow emits real evidence after the actual analyzer action runs. It records action outcome, exit code, severity-1/severity-2 counts, exact release-candidate SHA, and run provenance. The analyzer gate remains independent and still fails the workflow when appropriate.

For pull requests, evidence is bound to `github.event.pull_request.head.sha`, not the synthetic merge-ref `GITHUB_SHA`. That distinction matters when artifacts from independent workflows are joined by commit identity.

### Authenticated Apex/runtime

`.github/workflows/apex-runtime.yml` is the real org-backed runtime producer. When the two required repository secrets are present, it installs Salesforce CLI, authenticates the target org, runs `OpportunityReleaseGuardTest`, retains the raw Salesforce JSON result, and invokes `tools/apex_runtime_evidence.py` to produce the shared SHA-bound supporting-evidence artifact.

Required GitHub Actions secrets:

```text
SF_INSTANCE_URL   My Domain or Salesforce instance URL
SF_ACCESS_TOKEN   access token for the CI runtime user
```

Salesforce CLI supports non-interactive CI authentication through `SF_ACCESS_TOKEN` plus `sf org login access-token --no-prompt`. The runtime command uses `sf apex run test --class-names OpportunityReleaseGuardTest --wait 20 --result-format json --json`. The CI user must have the Salesforce permissions required to execute Apex tests.

The repository never stores either credential. When the secrets are absent, the workflow emits no runtime artifact. That absence remains visible to the aggregator as missing evidence; it is never converted into a fixture pass.

The resulting evidence is emitted with:

```text
source       salesforce-apex-runtime
runtime_kind authenticated-apex-tests
fixture      false
status       passed | failed
git_sha      exact pull-request head SHA
run_id/url   GitHub Actions provenance
```

`tools/apex_runtime_evidence.py` remains dependency-free and does not authenticate or execute Salesforce by itself. It only serializes the result supplied by the authenticated workflow.

## Release bundle CLI

```bash
python tools/bgstm_release_evidence.py \
  --pr-impact evidence/pr-native-impact.json \
  --project-id 00000000-0000-0000-0000-000000000039 \
  --git-sha abc123 \
  --git-branch feature/example \
  --ci-url https://github.com/example/repo/actions/runs/123 \
  --code-analyzer-evidence evidence/code-analyzer-evidence.json \
  --apex-runtime-evidence evidence/apex-runtime-evidence.json \
  --orchestration-provenance evidence/orchestration-plan.json \
  --json-out evidence/bgstm-release-evidence.json \
  --text-out evidence/bgstm-release-evidence.txt
```

Both supporting cases preserve accepted source provenance inside the generated BGSTM case template. When orchestration provenance is supplied, the bundle also retains the upstream workflow/run selections in `source_summary.orchestration` without changing the release-decision rules.

## Cross-workflow orchestration

`.github/workflows/release-evidence.yml` joins evidence produced by three independent GitHub Actions workflows. It is triggered after `PR Change Impact`, `Salesforce Code Analyzer`, or `Salesforce Apex Runtime` completes.

The orchestrator:

1. takes the triggering workflow's `head_sha` as the release-candidate identity;
2. queries completed runs of all three upstream workflows for that exact SHA;
3. uses `tools/workflow_evidence_plan.py` to choose the latest matching completed run for each source;
4. downloads only the expected named artifacts;
5. treats the downloaded files strictly as data and never executes them;
6. invokes the existing release aggregator with whichever validated evidence artifacts are present;
7. uploads one `bgstm-release-evidence` artifact containing the bundle, text summary, run-selection plan, and collected source data.

A failed upstream run is not automatically discarded. A failed PR Change Impact run may be the expected manifestation of a semantic `NO-GO`; a failed Code Analyzer run may contain the evidence that should block release; and a failed Apex Runtime run can provide authoritative runtime failure evidence. The artifact content remains authoritative and is independently validated by the aggregator.

### Interim REVIEW and convergence

The three upstream workflows finish independently, so early orchestration runs can legitimately produce `REVIEW` while one or more required artifacts are not yet available. Every upstream completion retriggers orchestration, which re-queries all three workflows for the exact same release SHA.

```text
first upstream completes
        ↓
partial evidence
        ↓
REVIEW is acceptable

later upstream completes
        ↓
re-query exact SHA
        ↓
fuller evidence set
        ↓
GO / REVIEW / NO-GO recomputed
```

A fully evidenced safe change can now converge to:

```text
semantic business-intent check   PASSED
Salesforce Code Analyzer         PASSED
authenticated Apex runtime       PASSED
---------------------------------------
release decision                 GO
```

A demonstrated semantic failure still has stronger precedence and remains `NO-GO` even when both supporting signals pass.

### Orchestration security boundary

The orchestration workflow uses only:

```text
actions: read
contents: read
```

It checks out trusted `main` orchestration code rather than PR-head code, uses the repository-scoped `GITHUB_TOKEN`, downloads only exact artifact names into temporary directories, and never executes downloaded content. The selected runs must match the exact release SHA, and supporting evidence is independently checked again for its embedded SHA before being trusted.

Salesforce credentials are available only to the dedicated runtime workflow as GitHub Actions secrets. They are not passed into the orchestrator or stored in artifacts.

## Credential-free demo vs real runtime

Demo CI deliberately uses deterministic fixtures bound to its own `GITHUB_SHA` to prove ingestion and release-decision machinery. The Apex fixture is explicitly marked `fixture: true`. This is **not** an assertion that Apex ran in a Salesforce org.

The real path is:

```text
authenticated Salesforce org
        ↓
OpportunityReleaseGuardTest
        ↓
actual Salesforce CLI pass/fail
        ↓
apex_runtime_evidence.py
        ↓
SHA-bound artifact
        ↓
cross-workflow collection
        ↓
validated BGSTM release bundle
```

If authenticated credentials are not configured, no runtime artifact is emitted. Safe semantic + Code Analyzer evidence therefore remains `REVIEW`; the system never manufactures a runtime success.

## BGSTM upload sequence

1. `POST /api/v1/external-results/session` with `session_request`.
2. Read the returned session UUID.
3. Add that UUID as `session_id` to every case template.
4. `POST /api/v1/external-results/case` for each case.
5. `PATCH /api/v1/external-results/session/{session_id}` with `finish_session_request`.

Semantic cases retain `requirement_external_ids`; supporting Code Analyzer and Apex/runtime cases remain release-wide evidence. New runtime/UI cases can later carry requirement IDs where the evidence is requirement-specific.
