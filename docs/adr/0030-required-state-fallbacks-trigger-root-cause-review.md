# ADR 0030: Required-state fallbacks trigger root-cause review

- Status: accepted
- Date: 2026-09-07

## Context

The frozen Locust #3207 run exposed a repeatable failure mode. The Implementer changed a required
mapping lookup into `.get(..., fallback)`. The public tests passed, and two independent Reviewers
accepted the Patch even though a precommitted CPython 3.13 evaluator still reproduced the defect.
The second Reviewer received twice the read-tool budget, so lack of browsing capacity was not a
sufficient explanation.

The Patch changed the consumer where the exception surfaced. It did not repair the earlier object
ownership/lifetime violation that caused required request metadata to disappear. A generic rule
that rejects every `.get()` change would produce false blocks because optional mapping state and
explicit fallback semantics are common.

## Decision

PRGuard will add two complementary, bounded controls:

1. Implementer and Reviewer instructions require tracing missing keys, attributes, objects, or
   lifecycle-sensitive state to their producer, ownership, aliasing, mutation, and release points.
2. Base/Candidate Python analysis emits a deterministic review signal when a required string-key
   subscript in a changed public callable is reduced while a `.get()` access for the same expression
   and key is added.

The signal is evidence for further inspection, not a verdict. The Reviewer may accept a fallback
when the Issue or repository contract establishes that absence is valid and defines the fallback
semantics. The Harness remains responsible only for deterministic execution and policy gates.

## Consequences

- This catches the exact structural shape that the Locust false accept lacked, at low cost and
  without executing repository code.
- The analysis is intentionally incomplete: it does not prove alias identity, data flow, concurrency
  behavior, or correctness of arbitrary exception handling.
- The Locust case is contaminated after evaluator reveal. It can validate that the new signal is
  produced, but it cannot become fresh held-out evidence for improved Reviewer accuracy.
- The next accuracy claim requires a new frozen case and precommitted evaluator.
