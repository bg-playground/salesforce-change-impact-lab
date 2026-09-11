# Safe PR-native impact proof

This branch intentionally changes a governed Salesforce validation rule without changing its business semantics.

Expected CI behavior:

- detect the validation-rule metadata in the real pull-request diff;
- map it to `SF-OPP-001` as a high-risk business control;
- select semantic contract and boundary evidence;
- evaluate the PR version of the metadata against the frozen `>20%` requirement;
- return `GO` because the implementation still enforces `>20%`.

A follow-up controlled drift pull request will change the implemented threshold to `>30%` and is expected to produce `NO-GO` without being merged.
