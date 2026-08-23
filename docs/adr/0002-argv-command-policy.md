# ADR 0002: Use argv-only verification commands

Status: Accepted (2026-08-18)

Verification commands are lists of strings, never shell source. A global grammar permits pytest
and non-mutating `ruff check --no-fix` forms; a per-task allowlist must also match exactly.
Absolute/path-traversing arguments, mutating Ruff forms, and shell interpreters are rejected. This
is intentionally less flexible than a free shell and keeps command authority explicit and
auditable.
