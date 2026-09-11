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

## Live Salesforce Code Analyzer evidence

The Salesforce Code Analyzer workflow now emits `code-analyzer-evidence.json` after the actual analyzer action runs. The evidence records:

- schema and source identity;
- normalized `passed` / `failed` status;
- exact Git commit SHA;
- workflow and run provenance;
- analyzer action outcome, exit code, and severity-1/severity-2 counts.

The workflow uploads this small release-evidence file separately from the analyzer's native detailed-results artifact. The analyzer action uses `continue-on-error` only so evidence can always be written and uploaded; the final gate step preserves the existing behavior and fails the workflow for analyzer/action failure or critical/high findings.

The release aggregator accepts the evidence only when its schema, source, status, and expected Git SHA are valid. Missing, malformed, or SHA-mismatched evidence is normalized to `not-run`, which produces `REVIEW` unless a stronger `NO-GO` already exists. This prevents evidence from a different release candidate from being trusted accidentally.

## CLI

```bash
python tools/bgstm_release_evidence.py \
  --pr-impact evidence/pr-native-impact.json \
  --project-id 00000000-0000-0000-0000-000000000039 \
  --git-sha abc123 \
  --git-branch feature/example \
  --ci-url https://github.com/example/repo/actions/runs/123 \
  --code-analyzer-evidence evidence/code-analyzer-evidence.json \
  --apex-runtime passed \
  --json-out evidence/bgstm-release-evidence.json \
  --text-out evidence/bgstm-release-evidence.txt
```

Apex/runtime remains a normalized input in this increment. It is intentionally the next supporting signal to migrate to the same evidence-file pattern.

## Evidence production vs orchestration

This increment establishes **production and validation of real Code Analyzer evidence**. It does not yet make one GitHub Actions workflow download another workflow's artifact. Cross-workflow orchestration is a separate concern and should not be hidden inside the offline aggregator.

Demo CI therefore creates a deterministic Code Analyzer evidence fixture for the current `GITHUB_SHA` to exercise the same ingestion path. The actual Salesforce Code Analyzer workflow produces the real artifact whenever governed `force-app/**` metadata changes. A later orchestration step can download that artifact and pass it to the unchanged aggregator interface.

## Bundle shape

The generated JSON contains the release decision/reason, source summary, BGSTM session request, requirement-linked case templates, finish-session request, and upload sequence. Semantic cases retain `requirement_external_ids` such as `SF-CASE-001`; Code Analyzer and Apex/runtime remain release-wide supporting cases.

The Code Analyzer BGSTM case now preserves the ingested provenance in its `source` object, including the validated Git SHA and run information, instead of representing the check as a hard-coded status.

## BGSTM upload sequence

1. `POST /api/v1/external-results/session` with `session_request`.
2. Read the returned session UUID.
3. Add that UUID as `session_id` to every case template.
4. `POST /api/v1/external-results/case` for each case.
5. `PATCH /api/v1/external-results/session/{session_id}` with `finish_session_request`.

The offline bundle remains credential-free while preserving a direct path to live BGSTM submission.

## Future evidence sources

The same pattern should next be applied to actual Apex/runtime evidence, followed by targeted Playwright journeys carrying the same requirement IDs and richer artifact references such as logs, traces, and screenshots. New evidence should enrich the release record without weakening semantic decision precedence.
