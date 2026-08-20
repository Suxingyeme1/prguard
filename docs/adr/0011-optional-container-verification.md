# ADR 0011: Container verification is explicit, immutable, and fail closed

Status: Accepted (2026-08-20)

## Context

The detached Git worktree protects normal developer workflow but does not isolate hostile test
code from the host kernel, network, filesystem, or process resources. Making every run depend on a
container would break existing trusted local workflows and hide environment failures behind test
failures.

## Decision

Keep host execution as the default and add an explicit `container` object to Task contracts. A
container run must:

- reference an image by `sha256` digest or local image ID and use `--pull=never`;
- run with a non-root numeric UID/GID;
- deny networking, drop every capability, and enable `no-new-privileges`;
- mount the detached worktree read-only and use tmpfs for HOME and TMP;
- use a read-only root filesystem plus CPU, memory, and PID limits;
- override any image entrypoint with the allowlisted `python -m pytest/ruff` argv;
- retain command and task deadlines, and forcibly remove a timed-out container by cidfile;
- emit and strip an internal Python-start marker so runtime launch failures remain distinct from
  product-test exit codes even when a Docker distribution returns the ambiguous exit code `1`;
- record backend, image, and infrastructure errors in the normal VerificationResult Artifact.

Docker is invoked as an argv array with `shell=False`. Engine/image launch failures are
infrastructure failures, not failing product tests.

## Consequences

Project-specific dependencies must be present in the selected image; PRGuard never installs them
during verification. Read-only worktrees can reject test suites that expect to generate files
inside the repository, so those tasks must be adapted to use TMP or remain trusted host-mode runs.

Access to a Docker daemon is itself privileged and remains part of the trusted Harness/orchestrator
boundary. PRGuard does not mount the daemon socket into the verification container and does not
recommend adding the runtime user to a rootful Docker group.
