# Container-backed verification

PRGuard can run declared pytest/Ruff commands in a digest-pinned Docker image. This mode is
explicit per Task; trusted local tasks continue to use the host executor by default.

## Build the reference image

The reference image contains Python 3.12, pytest, and Ruff. The base image is digest-pinned and all
Python wheels are hash-locked:

```bash
docker build -t prguard-verifier:python312 containers/python312
docker image inspect prguard-verifier:python312 --format '{{.Id}}'
```

For an air-gapped build, place the six wheels named in `requirements.lock` under
`containers/python312/wheelhouse/`, verify their hashes, and run:

```bash
docker build \
  -f containers/python312/Dockerfile.offline \
  -t prguard-verifier:python312 \
  containers/python312
```

Use the resulting full `sha256:...` image ID in the Task. Tags alone are rejected.

Run the boundary probe against that exact image:

```bash
uv run python scripts/run_container_security_probe.py --image "$(
  docker image inspect prguard-verifier:python312 --format '{{.Id}}'
)"
```

The probe is opt-in because CI environments do not necessarily expose a Docker daemon. It checks
the declared non-root, privilege, capability, mount, network, and cgroup controls and emits a normal
SHA-256 Manifest.

## Task fragment

```json
{
  "container": {
    "engine": "docker",
    "image": "sha256:<64 lowercase hex characters>",
    "python_executable": "python3",
    "memory_mb": 1024,
    "cpus": 1.0,
    "pids_limit": 128
  }
}
```

The fixed fields `network=none`, `read_only_root=true`, `read_only_worktree=true`, and the default
non-root user cannot be weakened through Task JSON. Project dependencies must already exist in the
image; verification never performs a package install or image pull.

## Operational boundary

Run the Harness under a trusted orchestrator. A rootful Docker socket is root-equivalent; do not
make it available to Agent/model code and do not mount it into the test container. Rootless Docker
or Podman and a dedicated worker VM provide a stronger production boundary.

Container mode reduces filesystem, credential, network, fork-bomb, and resource-exhaustion risk.
It does not protect against container-runtime/kernel vulnerabilities, a malicious image, daemon
misconfiguration, or denial of service against the Docker daemon. The exact image ID and
VerificationResult remain part of the replayable Artifact.

## Validation record

On 2026-08-20, Docker Desktop 29.5.3 ran the reference ARM64 image with every declared control.
The normal fix fixture passed two pytest checks through the container backend, and the security
probe confirmed non-root UID, `NoNewPrivs=1`, zero effective capabilities, read-only root/worktree,
writable private tmpfs paths, no network route, and the declared cgroup limits. Both runs left zero
containers and produced verifiable Manifests.

Ubuntu's snap-packaged Docker 29.6.1 rejected Python startup whenever
`no-new-privileges` was enabled. PRGuard did not retry with weaker controls: the command timed out,
the container was removed, and the run failed closed. Runtime compatibility is therefore part of
worker qualification, not a reason to silently relax Task policy.
