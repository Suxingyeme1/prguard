# ADR 0025: disambiguate edits and Base-probe Agent-authored tests

- Status: accepted
- Date: 2026-09-04

## Context

An exact text replacement safely rejects duplicate snippets, but rejection alone makes ordinary
multi-occurrence code awkward to edit. Separately, executing a newly written test on Candidate does
not prove that the test detects the original defect; a vacuous test can pass on both Base and
Candidate.

## Decision

Keep unique `replace_text`, and add two declarative alternatives:

- `replace_lines` targets an inclusive line range and SHA-256 of the bytes returned by `read_file`;
- `replace_python_symbol` targets one unambiguous AST definition and the SHA-256 of that definition.

The Harness owns application, checks the hash immediately before editing, and syntax-checks a
Python-symbol result. Git still produces the final Patch.

For candidate Fix/Review workflows, executable changes to conventional Python test modules must be
copied onto a fresh unchanged Base worktree and fail there before Candidate verification. Candidate
source changes are withheld. Python AST-equivalent comment or formatting changes do not require
FAIL_TO_PASS evidence.

## Consequences

Repeated source text can be edited deliberately without granting arbitrary writes, and stale
line/symbol observations fail closed. Agent-authored tests now need basic regression evidence.
Neither mechanism proves semantic correctness: line numbers can be coarse, static symbols do not
cover generated/dynamic code, and an incorrectly specified test may still fail on Base.
