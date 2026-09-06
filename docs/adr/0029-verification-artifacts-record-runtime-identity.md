# ADR 0029: verification artifacts record runtime identity

Status: accepted 2026-09-06.

## Context

A Base Commit, Patch hash, and pytest argv do not fully identify a verification result when behavior
depends on the Python implementation or version. Prior Harness artifacts recorded host/container
selection and image digest, but a host result could not prove whether it used Python 3.12 or 3.13.

## Decision

Each launched verification result records Python implementation, version, cache tag, platform,
architecture, executable basename, and whether the identity came from the host process or the
container process. Host execution uses the exact interpreter running PRGuard. Container execution
emits its identity before replacing the bootstrap process with pytest/Ruff; a missing or malformed
identity marker is an infrastructure failure. Absolute executable paths are not archived.

The host command environment prepends the active interpreter's script directory to `PATH`, so
repository tests that invoke an installed console entry point observe the same environment as
`python -m pytest`. The fixed command allowlist and `shell=False` boundary are unchanged.

## Consequences

The same frozen FixTask can be checked with `prguard gate` under multiple Python interpreters, and
each Manifest is independently attributable to its runtime. This records evidence; it does not
automatically create environments, install dependencies, or claim that two lanes are a complete
compatibility matrix.
