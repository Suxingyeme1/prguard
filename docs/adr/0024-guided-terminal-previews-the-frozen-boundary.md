# ADR 0024: guided terminal previews the frozen boundary

- Status: accepted
- Date: 2026-09-04

## Context

The automation-oriented CLI already accepts natural-language local Issues, but a new user must know
several flags before seeing what PRGuard will run. Hiding those decisions behind an Agent would be
worse: Base selection, verification commands, writable paths, and host/container trust are policy,
not semantic suggestions.

## Decision

Add `prguard start` as a dependency-free, line-oriented terminal entry. It gathers Issue text,
resolves and displays the exact Base Commit, previews deterministic project discovery, and requires
an explicit execution boundary plus final confirmation. `--yes` removes only the confirmation; it
does not choose host trust on the user's behalf.

After approval, the entry calls the existing local preparation and FixRunner workflows. It does not
maintain a parallel Task format, run commands directly, or give the model additional capabilities.

## Consequences

The common local path is understandable over an ordinary terminal or SSH session while the JSON
contract remains available for CI and replay. The UI is intentionally not a full-screen editor or
web service; cancellation, non-interactive use, and unsupported project policies remain explicit.
