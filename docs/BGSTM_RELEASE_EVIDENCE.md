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

Both release-wide supporting signals now use the same evidence contract:

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

The Code Analyzer workflow emits real evidence after the actual analyzer action runs. It records action outcome, exit code, severity-1/severity-2 counts, exact Git SHA, and run provenance. The analyzer gate remains independent and still fails the workflow when appropriate.

### Apex/runtime

`tools/apex_runtime_evidence.py` is a dependency-free producer for authenticated runtime workflows. It does **not** execute Salesforce tests itself. A future scratch-org or authenticated CI job runs the real Apex/Flow runtime command, determines `passed` or `failed`, then invokes the producer with that result and the current Git SHA.

Example after a real Apex test run:

```bash
python tools/apex_runtime_evidence.py \
  --status passed \
  --git-sha "$GITHUB_SHA" \
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
  --json-out evidence/bgstm-release-evidence.json \
  --text-out evidence/bgstm-release-evidence.txt
```

Both supporting cases preserve accepted source provenance inside the generated BGSTM case template.

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
validated BGSTM release bundle
```

Keeping that boundary explicit makes the public demo reproducible without credentials while preventing simulated evidence from being confused with org-backed execution.

## Evidence production vs orchestration

Code Analyzer now produces a real workflow artifact, while Apex/runtime has a production-ready evidence producer for a future authenticated workflow. This increment does not make one workflow discover/download another workflow's artifact. Cross-workflow orchestration remains the next separate concern.

## BGSTM upload sequence

1. `POST /api/v1/external-results/session` with `session_request`.
2. Read the returned session UUID.
3. Add that UUID as `session_id` to every case template.
4. `POST /api/v1/external-results/case` for each case.
5. `PATCH /api/v1/external-results/session/{session_id}` with `finish_session_request`.

Semantic cases retain `requirement_external_ids`; supporting Code Analyzer and Apex/runtime cases remain release-wide evidence. New runtime/UI cases can later carry requirement IDs where the evidence is requirement-specific.
