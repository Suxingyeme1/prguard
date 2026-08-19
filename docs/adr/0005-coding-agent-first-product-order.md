# ADR 0005: Deliver repository coding before independent review

Status: Accepted (2026-08-18)

PRGuard's first identity is a Coding Agent for real repositories. The primary entry is `fix`, from
Issue to tested patch; `review` is a later quality module. Therefore Phase 2 implements one
Implementer with repository search, bounded reads/edits, deterministic tests, and one repair before
adding the Independent Reviewer. Planning stays inside the Implementer and test execution remains
deterministic. Evaluation stays small and reproducible until the product paths work end to end.

