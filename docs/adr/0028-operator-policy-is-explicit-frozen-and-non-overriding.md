# ADR 0028: operator policy is explicit, frozen, and non-overriding

Status: accepted 2026-09-06.

## Context

Some real repositories have no `.prguard.toml`, and conservative discovery can find a test tree
whose full invocation needs generated assets, optional services, or other environment preparation.
Editing the upstream checkout to add PRGuard configuration would violate the immutable Base Commit;
editing generated Task JSON by hand is error-prone and obscures policy provenance.

## Decision

GitHub/local preparation, policy inspection, and guided execution may receive an explicit local
`--policy-file`. It uses the same strict `ProjectConfig`, pytest/Ruff argv grammar, path validation,
fixed protected paths, and timeout bounds as repository-owned policy. Preparation serializes the
validated values as `operator-policy.json` and includes that file in the preparation Manifest.

An operator policy cannot override a repository-owned `.prguard.toml`; ambiguous precedence fails
closed. The file is configuration from a trusted human or CI boundary, never model output. It does
not install dependencies or grant shell execution.

## Consequences

External repositories can receive a reviewed, reproducible gate without changing the frozen Git
tree. Reviewers can distinguish deterministic discovery, repository policy, and operator policy in
artifacts. The operator remains responsible for making the gate representative; a narrow passing
gate is evidence only for the declared checks.
