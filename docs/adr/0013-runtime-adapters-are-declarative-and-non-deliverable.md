# ADR 0013: Runtime adapters are declarative and non-deliverable

Status: Accepted (2026-08-23)

## Context

A clean Git checkout is not always a runnable Python test environment. Build backends can generate
modules during installation, and repositories can keep optional test plugins outside core
dependencies. Blindly running every test after a model proposal misclassifies these setup failures
as Patch failures and wastes the one repair round. Automatically installing arbitrary project
dependencies would execute a much broader capability and make runs less reproducible.

## Decision

Before any Implementer call, run the declared pytest targets in `--collect-only` mode and declared
non-pytest gates against the Base Commit through the normal deterministic Harness. Failing pytest
assertions do not block a Fix task; import, plugin, syntax, collection, and baseline quality-gate
failures do.

During GitHub onboarding, use explicit Issue symbol anchors and the bounded Python index to select
the strongest related public test file when one exists. Keep `.prguard.toml` as the reviewed source
of truth when a repository needs a wider or different gate.

Support one narrow build adapter: when `pyproject.toml` explicitly declares a missing Hatch VCS
`version-file`, record a `0.0.0` runtime-file specification in the Task. The Harness creates it only
inside detached execution worktrees, protects the path from candidate edits, verifies its hash
after commands, and excludes it from changed files and the Base-relative final diff.

## Consequences

Collection readiness and the Humanize-style generated-version case no longer consume model tokens
or create false repairs. The runtime scaffold is visible in Task and Artifact JSON, so replay does
not depend on hidden host state.

This is not a general package installer. Missing dependencies, services, compiled extensions, or
other build-generated APIs still fail closed and require a reviewed project profile or container
image. Issue-related test targeting is a conservative first gate, not a substitute for a wider
maintainer regression suite.
