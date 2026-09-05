# FileLock #606 held-out Issue case

Frozen: 2026-09-04

This package records preparation of a new real-repository Issue-to-Patch case for
[tox-dev/filelock #606](https://github.com/tox-dev/filelock/issues/606). The Agent-facing Issue
describes only the required exception-preservation behavior. The upstream repair, later Pull
Request, and evaluator material are excluded from the Task and this public package.

The source archive is bound to upstream commit
`94a80aa72b07bf810e5e7fed4b89eed137e8a9f9`. PRGuard's deterministic discovery selected unfiltered
`pytest -q`, Python source/test write scopes, fixed protected paths, and a runtime-only Hatch VCS
version scaffold. A clean Base run passed **539 tests**, skipped 33, emitted six known filesystem
fallback warnings, and left the source checkout unchanged. The recursive raw Manifest verified.

This is a staged holdout, not a claimed model success. No live Implementer run is recorded because
provider credentials were unavailable in the local execution environment and the authorized
remote host was unreachable. That missing observation is explicit in `case-summary.json`; it must
not be converted into an accepted result or silently replaced with a scripted proposal.

The next valid step is to run the frozen natural-language Issue through a live provider without
opening the evaluator package, then attach the evaluator only after the candidate Patch and raw
Manifest have been frozen. An accepted candidate must pass the repository gate and any changed
Agent-authored test must also demonstrate FAIL_TO_PASS behavior on the unchanged Base.
