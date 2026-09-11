# BGSTM-compatible release evidence

Salesforce Change Impact Lab rolls requirement-aware semantic evidence together with supporting release signals into a deterministic handoff bundle aligned with BGSTM External Results v1. The adapter makes no BGSTM network calls and requires no Salesforce org credentials.

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

### Apex/runtime

`tools/apex_runtime_evidence.py` is a dependency-free producer for authenticated runtime workflows. It does **not** execute Salesforce tests itself. A future scratch-org or authenticated CI job runs the real Apex/Flow runtime command, determines `passed` or `failed`, then invokes the producer with that result and the current release-candidate SHA.

Example after a real Apex test run:

```bash
python tools/apex_runtime_evidence.py \
  --status passed \
  --git-sha "$RELEASE_CANDIDATE_SHA" \
  --runtime-kind apex-tests \
  --run-id "$GITHUB_RUN_ID" \
  --run-url "https://github.com/$GITHUB_REPOSITORY/actions/runs/$GITHUB_RUN_ID" \
  --total 12 --passed 12 --failed 0 \
  --json-out evidence/apex-runtime-evidence.json
```

The producer can also represent Flow runtime or another org-backed execution via `--runtime-kind` without changing the release-bundle schema.

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

`.github/workflows/release-evidence.yml` joins evidence produced by independent GitHub Actions workflows. It is triggered after either `PR Change Impact` or `Salesforce Code Analyzer` completes.

The orchestrator:

1. takes the triggering workflow's `head_sha` as the release-candidate identity;
2. queries completed runs of both upstream workflows for that exact SHA;
3. uses `tools/workflow_evidence_plan.py` to choose the latest matching completed run for each source;
4. downloads only the expected named artifacts;
5. treats the downloaded files strictly as data and never executes them;
6. invokes the existing release aggregator with the collected evidence;
7. uploads one `bgstm-release-evidence` artifact containing the bundle, text summary, run-selection plan, and collected source data.

A failed upstream run is not automatically discarded. A failed PR Change Impact run may be the expected manifestation of a semantic `NO-GO`, and a failed Code Analyzer run may contain the evidence that should block release. The evidence inside the artifact remains authoritative and is validated by the aggregator.

### Interim REVIEW and convergence

The two upstream workflows finish independently, so the first completion can trigger orchestration before the second artifact exists. That first aggregation may legitimately produce `REVIEW` because required evidence is missing.

When the second upstream workflow completes, `workflow_run` triggers orchestration again. The new run re-queries both workflows for the same SHA and converges on the fuller evidence set.

```text
first upstream completes
        ↓
partial evidence
        ↓
REVIEW is acceptable

second upstream completes
        ↓
re-query same SHA
        ↓
fuller evidence set
        ↓
GO / REVIEW / NO-GO recomputed
```

This avoids polling and does not convert absence into a false pass.

### Orchestration security boundary

The orchestration workflow uses only:

```text
actions: read
contents: read
```

It checks out trusted `main` orchestration code rather than PR-head code, uses the repository-scoped `GITHUB_TOKEN`, downloads only exact artifact names into temporary directories, and never executes downloaded content. The selected runs must match the exact release SHA, and supporting evidence is independently checked again for its embedded SHA before being trusted.

No PAT, Salesforce credential, BGSTM runner token, or other long-lived secret is introduced.

## Credential-free demo vs real runtime

Demo CI deliberately uses deterministic fixtures bound to its own `GITHUB_SHA` to prove the ingestion and release-decision machinery. The Apex fixture is explicitly marked `fixture: true`. This is **not** an assertion that Apex ran in a Salesforce org.

The real production path is:

```text
authenticated Salesforce runtime test
        ↓
actual pass/fail result
        ↓
apex_runtime_evidence.py
        ↓
SHA-bound evidence artifact
        ↓
cross-workflow collection
        ↓
validated BGSTM release bundle
```

Until that authenticated runtime workflow exists, the orchestrator intentionally supplies no Apex/runtime artifact. The release bundle therefore remains `REVIEW` when the semantic and Code Analyzer evidence pass, rather than manufacturing a runtime success.

## BGSTM upload sequence

1. `POST /api/v1/external-results/session` with `session_request`.
2. Read the returned session UUID.
3. Add that UUID as `session_id` to every case template.
4. `POST /api/v1/external-results/case` for each case.
5. `PATCH /api/v1/external-results/session/{session_id}` with `finish_session_request`.

Semantic cases retain `requirement_external_ids`; supporting Code Analyzer and Apex/runtime cases remain release-wide evidence. New runtime/UI cases can later carry requirement IDs where the evidence is requirement-specific.
