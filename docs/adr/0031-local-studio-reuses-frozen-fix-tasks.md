# ADR 0031: Local Studio approves a frozen FixTask

## Status

Accepted. Extends the static replay boundary in ADR 0026 (Studio).

## Decision

`prguard studio` serves the existing static application through a standard-library HTTP adapter
bound only to `127.0.0.1`. A random per-process token arrives in a URL fragment and authenticates
all API requests using an Authorization header. Exact Host/Origin checks, no CORS, no directory
listing, a fixed static asset map, bounded JSON bodies, and strict request schemas protect the
local execution entry from unrelated websites and path/command injection.

The CLI selects a single repository, provider, optional reviewed policy, workspace, and explicit
host/container boundary. The browser submits only mode, Issue, and requested Git version.
Preparation calls existing local onboarding and retains the serialized FixTask in process memory;
its SHA-256, commit, commands, paths, and limits are shown before an explicit start request. A
changed on-disk prepared Task is rejected. A later source HEAD or policy edit cannot replace the
already-approved Task. Preparation performs Git materialization and static policy discovery, not
model calls or repository test execution.

One worker runs the existing FixRunner with its normal provider and Harness. Its ordered progress
events are exposed by short polling; the connection carries observation, not execution control.
Refreshing retrieves the current run without resubmitting it. Starting twice or concurrently is a
conflict. Sessions have a 50-task cap; event and response/file sizes are bounded. A disconnected
browser is not cancellation. Closing Studio waits for the bounded task to finish artifact writes.

Delivery verifies the recursive Fix Manifest. Download names are server-owned and resolve only
to selected files in that run. Each download is a regular non-symlink file with the exact recorded
hash; known provider secrets block file delivery rather than modifying hash-bound content. UI
snapshots redact the configured provider secrets. The host backend remains trusted code execution,
not an OS sandbox; the adapter does not change the Harness trust model.

The default fixture runs the same real Git/pytest failure-repair path as the terminal demo, using
scripted model proposals. Configured-repository mode uses the normal live provider. Neither mode
claims Reviewer execution: the browser Fix result explicitly records `review_status: not_run`.
The static hosted site retains read-only evidence replay and instructions for launching the local
adapter, with no connection to the user's machine.

## Consequences

The frontend now demonstrates actual execution and can start real local repository fixes without
new web dependencies. Authentication and run-scoped artifacts are exercised through real HTTP
tests. Multi-user hosting, remote machine access, browser cancellation, persistent job recovery
after a server restart, and browser-controlled independent review remain separate future work.
