# BGSTM-compatible release evidence

Salesforce Change Impact Lab can roll its requirement-aware semantic evidence together with supporting release signals and emit a deterministic handoff bundle aligned with the BGSTM External Results v1 contract.

This is an **offline adapter**, not a BGSTM client. It makes no network calls, stores no runner token, and does not require a Salesforce org. Its job is to turn independent quality signals into one auditable release decision plus submission-ready payload templates.

## Why this layer exists

The lab now answers three different quality questions:

1. Is the testing machinery itself healthy?
2. Is the Salesforce implementation structurally/static-analysis valid?
3. Does the implementation still satisfy frozen business intent?

PR #38 proved those signals can disagree in a meaningful way: ordinary Demo CI and Salesforce Code Analyzer can pass while the business-intent gate correctly rejects the release candidate.

The release-evidence layer preserves that distinction rather than flattening everything into a generic pass/fail counter.

## Decision precedence

The roll-up is intentionally conservative:

```text
business-intent NO-GO              -> NO-GO
required supporting signal failed  -> NO-GO
required evidence missing          -> REVIEW
all required supplied evidence OK  -> GO
```

A passing Code Analyzer or Apex/runtime signal can never override a semantic `NO-GO`.

## CLI

```bash
python tools/bgstm_release_evidence.py \
  --pr-impact evidence/pr-native-impact.json \
  --project-id 00000000-0000-0000-0000-000000000039 \
  --git-sha abc123 \
  --git-branch feature/example \
  --ci-url https://github.com/example/repo/actions/runs/123 \
  --code-analyzer passed \
  --apex-runtime passed \
  --json-out evidence/bgstm-release-evidence.json \
  --text-out evidence/bgstm-release-evidence.txt
```

Supporting statuses are normalized to `passed`, `failed`, or `not-run`. `not-run` means required evidence is missing and therefore produces `REVIEW` unless a stronger `NO-GO` already exists.

Demo CI passes deterministic `passed` fixture statuses to prove bundle generation. That CI step is **not** claiming to ingest the result of the separate Salesforce Code Analyzer workflow. A future orchestration increment can supply actual workflow outcomes without changing the bundle schema.

## Bundle shape

The generated JSON contains:

- `release_decision` and `release_reason`;
- `source_summary` showing the contributing signals;
- `bgstm_external_results_v1.session_request`;
- `bgstm_external_results_v1.case_templates`;
- `bgstm_external_results_v1.finish_session_request`;
- an explicit upload sequence.

Each semantic case has a stable external ID and links directly to the frozen requirement by BGSTM external ID:

```json
{
  "external_id": "salesforce-change-impact-lab:SF-CASE-001:semantic",
  "title": "SF-CASE-001 semantic business-intent check",
  "outcome": "failed",
  "duration_ms": 0,
  "error_message": "Business-intent drift detected; mismatches=2.",
  "requirement_external_ids": ["SF-CASE-001"],
  "auto_register_requirements": false
}
```

The tool also emits release-wide cases for Salesforce Code Analyzer and Apex/runtime evidence. These currently have an empty `requirement_external_ids` list because they are supporting release signals rather than requirement-specific evidence.

## Why case templates do not contain `session_id`

BGSTM External Results v1 creates the session first. The server returns the actual session UUID, and every case result submitted afterward must reference that UUID.

For that reason, the offline bundle contains **case templates** rather than pretending a session ID already exists. The intended upload sequence is:

1. `POST /api/v1/external-results/session` with `session_request`.
2. Read the returned session UUID.
3. Add that UUID as `session_id` to every case template.
4. `POST /api/v1/external-results/case` for each case.
5. `PATCH /api/v1/external-results/session/{session_id}` with `finish_session_request`.

This keeps the public demo credential-free while making the eventual live BGSTM integration straightforward.

## Requirement-centered evidence

Multi-control semantic evidence remains separate even though the release gets one final decision:

```text
SF-OPP-001 semantic evidence   -> passed
SF-CASE-001 semantic evidence  -> failed
Code Analyzer                  -> passed
Apex/runtime                   -> passed
                                  -----
Release                        -> NO-GO
```

That is important for BGSTM traceability: reviewers can see both the release-level decision and which frozen requirement caused it.

## Future evidence sources

The output model is designed to accept additional case templates without changing the release contract. Planned examples include:

- targeted Playwright journeys carrying the same `requirement_external_ids`;
- org-backed Flow runtime checks;
- richer Apex execution evidence;
- artifact references such as logs, screenshots, traces, and machine-readable reports.

Those additions should enrich the evidence set, not weaken the existing semantic decision precedence.
