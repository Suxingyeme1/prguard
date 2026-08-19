# ADR 0002: Use argv-only verification commands

Status: Accepted (2026-08-18)

Verification commands are lists of strings, never shell source. A global grammar permits only
pytest and ruff forms; a per-task allowlist must also match exactly. Absolute/path-traversing
arguments and shell interpreters are rejected. This is intentionally less flexible than a free
shell and keeps command authority explicit and auditable.
