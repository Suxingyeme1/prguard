# Locust #3207 compatibility holdout

Frozen: 2026-09-06 · Live Agent run: pending

This package records a fresh compatibility-focused Issue-to-Patch holdout for
[locustio/locust #3207](https://github.com/locustio/locust/issues/3207). The public Issue and exact
upstream Base Commit are Agent-visible. Later upstream changes, solution material, the evaluator
body, and its expected repair are excluded from the frozen Task.

The source is fixed at `5df19da06a0f8418d44094f3014ddee3b307bb55` (Locust 2.40.1). Initial
deterministic discovery correctly found the non-standard `locust/test` tree, but its full-suite
Base run was not accepted as a task gate: that suite expects separately built web UI assets and
console-script behavior not supplied by the frozen checkout, and it contains a timing-sensitive
assertion on this host. These are environment/test-readiness failures, not candidate regressions.

A human-reviewed operator policy therefore freezes the existing catch-response tests as the
public regression gate: `pytest -q locust/test/test_http.py -k catch_response`. PRGuard validates
the same strict argv grammar and protected-path rules used for repository-owned policy, records the
canonical policy in the preparation Manifest, and refuses to let an operator file override an
existing repository `.prguard.toml`.

The model-free `prguard gate` entry ran that identical frozen Task under CPython 3.12.13 and
3.13.12. Both lanes passed 12 tests with 17 deselected, left the checkout clean, and produced
verified Manifests carrying the actual interpreter identity. A separate evaluator was sealed
before any live Agent run: only its SHA-256 commitment is public here. On the unchanged Base it
passes under 3.12 and fails under 3.13, establishing a version-specific FAIL_TO_PASS target without
requiring Appian, an external service, or network access.

No Implementer or Reviewer quality claim is made yet. The next valid observation must use this
frozen Task, keep the evaluator unavailable to both Agents, archive the exact candidate Patch and
public gates first, and only then attach the committed evaluator across both runtimes.
