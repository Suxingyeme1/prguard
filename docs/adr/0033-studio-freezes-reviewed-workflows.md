# ADR 0033: Studio freezes reviewed workflows before approval

## Status

Accepted. Extends ADR 0031 and the Fix-only execution scope in ADR 0032.

## Decision

Studio offers `fix` and `reviewed_fix` through the existing runners. The latter is available only
when the operator starts the local service with `--enable-independent-review`. The browser selects
an enabled workflow during preparation, not at approval or after execution starts. The start
request still accepts only explicit confirmation.

The canonical `studio-approved-task-v2` envelope binds the resolved Task, selected workflow,
Reviewer provider/model/settings and any scripted Implementer, Reviewer and repair payloads.
Approval checks the saved envelope against its retained bytes. Altering the external scripted
files after preview cannot change an approved run. These fixture payloads are not inserted into
Agent context or offered as browser evidence downloads. Provider secrets remain in the server
environment, outside this envelope.

Reviewed tasks preserve the total Task timeout. Initial Fix receives 55% of the total, capped at
600 seconds; review receives 25%, capped at 300 seconds; repair uses the remaining task deadline.
The adapter rejects reviewed tasks with a total timeout below 15 seconds. These are deterministic
defaults, not experimentally optimized allocations. Studio uses the always-review routing policy
when the user explicitly selects review. Risk analysis remains visible without silently skipping
that requested review.

Independent review and its repair reuse `IssueToPRRunner`. They use fresh provider instances and
the existing read/edit boundaries. Optional progress callbacks carry allowlisted metadata; observer
exceptions are suppressed so presentation cannot change the authoritative outcome. UI events are
saved separately from the recursive run Manifest and are not presented as independently signed or
hash-bound evidence.

The adapter verifies the recursive Manifest before registering hash-checked downloads. A
non-accepted final outcome never exposes `final.patch`, even if initial Fix verification was green.
The UI distinguishes independent acceptance, requested changes, review failure and a repair that
passed final verification. The latter does not imply a second independent review pass.

## Session and presentation behavior

Authenticated `GET /api/runs` returns at most 50 summaries owned by this server process. It does
not enumerate historical output directories. Browser selection/reconnection uses request generations
to ignore stale responses. A lost approval response triggers a state read before another action.
There is one executing worker, no browser cancellation, and no cross-process history recovery.
Artifacts remain on disk when the service closes.

The file diff viewer only parses display rows. It escapes source text and preserves the original
Patch for copying/downloading. Old/new line numbers, additions/deletions and hunk markers are
presentation aids, not a replacement for `git apply` validation. Binary and unrecognized lines
remain visible as metadata. The viewer does not execute or render source as HTML.

## Consequences

The same local UI can demonstrate initial Fix, independent review, and controlled repair without
introducing an Agent service or changing the Harness. Key-free demos identify scripted model
responses throughout; they demonstrate orchestration and verification, not model quality. Live
model efficacy remains a separate evidence question. Persistent jobs, cancellation and standalone
candidate-Patch upload remain later product work.
