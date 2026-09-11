# Architecture

The lab separates **Salesforce-native correctness checks** from an **independent business-intent oracle**.

## Native layer

Use normal Salesforce controls: metadata deployment validation, Apex unit tests, LWC Jest tests, Salesforce Code Analyzer, Flow tests where applicable, and targeted E2E automation.

These answer whether the implementation is syntactically valid, internally correct, secure, deployable, and behaviorally functional.

## Intent layer

`policies/SF-OPP-001.json` freezes a human-readable business rule in machine-readable form. `tools/impact_lab.py` then reads the Salesforce validation-rule metadata, extracts the implemented discount threshold, compares it to the frozen threshold, generates business-boundary cases, evaluates those cases against both the contract and implementation, records mismatches, makes a deterministic release decision, and emits JSON/HTML evidence.

The implementation does not grade itself. The policy contract is the oracle.

## Why mutation is part of the demo

The `mutations/` directory contains valid Salesforce metadata that weakens the rule from `>20` to `>30`. Deployment can still succeed, unrelated tests can still pass, a low-discount UI happy path can still pass, and code coverage can remain unchanged. The business control is nevertheless weaker.

The lab catches this because it tests the rule's **meaning**, not just its execution mechanics.

## Production evolution

A fuller implementation could add a Salesforce formula parser, Metadata/Tooling API change discovery, Flow graph analysis, Apex dependency graphs, Git-diff-aware requirement mapping, BGSTM External Results v1 reporting, NAT-managed adaptive execution, and controlled mutation campaigns for Profiles, Permission Sets, Flows, validation rules, sharing rules, and Apex.
