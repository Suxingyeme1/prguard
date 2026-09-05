# FileLock #606 held-out Issue-to-Patch case

Frozen: 2026-09-04 · Evaluated: 2026-09-05

This package records preparation of a new real-repository Issue-to-Patch case for
[tox-dev/filelock #606](https://github.com/tox-dev/filelock/issues/606). The Agent-facing Issue
describes only the required exception-preservation behavior. The upstream repair, later Pull
Request, and evaluator material are excluded from the Task and this public package.

The source archive is bound to upstream commit
`94a80aa72b07bf810e5e7fed4b89eed137e8a9f9`. PRGuard's deterministic discovery selected unfiltered
`pytest -q`, Python source/test write scopes, fixed protected paths, and a runtime-only Hatch VCS
version scaffold. A clean Base run passed **539 tests**, skipped 33, emitted six known filesystem
fallback warnings, and left the source checkout unchanged. The recursive raw Manifest verified.

The live experiment kept the evaluator sealed until after the candidate Fix and independent
Reviewer artifacts were frozen. The first DeepSeek candidate added two regression-test modules,
but those tests imported a candidate-only private symbol and therefore failed during collection on
Base. That run exposed a weak FAIL_TO_PASS gate: pytest exit code 2 is infrastructure/collection
failure, not evidence that a test exercised the original defect. PRGuard now accepts only pytest
exit code 1 for this Base probe and allows the resulting evidence to drive the one permitted repair.

The controlled resume replayed that exact frozen candidate as attempt 0, then used a live DeepSeek
repair for attempt 1. The repaired tests collected on Base and produced eight assertion failures;
the candidate then passed **563 tests**, skipped 33, and passed all 24 changed tests. Both the Fix
and Review Manifests verified. A 12-read independent Reviewer accepted the candidate with two P3
findings after one bounded terminal-protocol recovery.

The sealed evaluator nevertheless rejected the Patch. The candidate changed the existing default
context-manager behavior globally; the upstream-compatible contract preserves the legacy default
and makes grouped exceptions an explicit opt-in policy. The evaluator tests could not even collect
because the candidate omitted that public policy API. This case is therefore a verified false
accept, not a Task Resolution success.

The result hardened three general boundaries: Base-probe exit-code semantics, bounded terminal
submission for both providers, and an explicit Reviewer check for unrequested changes to public
defaults. The case is not rerun against the same model after opening the evaluator, because that
would contaminate the holdout.
