# ADR 0004: Treat worktree isolation as non-security isolation

Status: Accepted (2026-08-18)

A detached worktree prevents normal verification from mutating the developer checkout and makes
diff capture deterministic. It does not constrain malicious native code. Phase 1 therefore uses
strict command grammar, sanitized environment, deadlines, and post-run audits while documenting
that hostile repositories require a later container sandbox.
