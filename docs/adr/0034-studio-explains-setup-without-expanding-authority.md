# ADR 0034: Studio explains setup without expanding authority

## Status

Accepted.

## Decision

Make first-run setup and recovery visible in the browser, while retaining terminal ownership of
repository paths, provider credentials, verification policy and execution environment. The page's
repository startup command is a fixed placeholder example with an explicit host-trust note. The
external-policy example is illustrative only and does not write files, select commands or approve
execution. It states that configuring a policy cannot create absent tests.

Approval includes the actual preparation report's policy source and warnings. Inferred commands
are distinguished from repository-owned and operator-supplied configurations. Discovery does not
claim Issue coverage or regression completeness.

Git preflight and policy-discovery exceptions carry stable recovery codes. The adapter walks only
explicit exception causes, with a depth bound and cycle detection, and emits only allowlisted
categories. Arbitrary error strings cannot become recovery codes. The UI maps codes to translated
explanations; it keeps the original redacted error under a disclosure for diagnosis. Guidance is
informational and never executed as Shell or sent as authority to an Agent.

The session retains the original submitted request separately from the resolved execution Task.
Returning from a failed preparation restores Issue, requested version and workflow to the form.
Preparing again creates a new record and still requires approval. Previous files and source
changes are never discarded automatically. Session restart recovery remains out of scope.

## Verification

Unit tests cover typed cause selection, unknown categories, text spoofing and cyclic causes.
HTTP integration tests cover missing/dirty repositories, unresolved versions, absent test gates,
preserved requests and policy provenance. Chromium browser tests execute the real loopback API,
Git and Harness with scripted providers. They check approval, review status, keyboard tabs,
language/source preservation, narrow layout, exact download hashes, refresh/history, recovery and
failed-review delivery blocking. The test-only launcher binds a random port and token, clears model
keys from the child environment, and owns only its temporary fixture tree. No test-reset endpoint
or fixed token is added to production Studio.

Playwright and Chromium are development-only. The shipped static UI adds no runtime dependency.
Failed-browser diagnostic files remain ignored locally and are not automatically published by CI.
