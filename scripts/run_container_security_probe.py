"""Run an opt-in, deterministic probe of the container verification boundary."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path
from uuid import uuid4

from prguard.harness import VerificationHarness, verify_manifest
from prguard.schemas import CommandSpec, ContainerExecutionSpec, RunOutcome, Task

_PROBE_TEST = '''\
import os
import socket
from pathlib import Path

import pytest


def _status_value(name: str) -> str:
    for line in Path("/proc/self/status").read_text().splitlines():
        if line.startswith(name + ":"):
            return line.split(":", 1)[1].strip()
    raise AssertionError(f"missing process status field: {name}")


def test_non_root_no_privileges_and_no_capabilities() -> None:
    assert os.geteuid() != 0
    assert _status_value("NoNewPrivs") == "1"
    assert int(_status_value("CapEff"), 16) == 0


def test_root_and_workspace_are_read_only() -> None:
    assert os.statvfs("/").f_flag & os.ST_RDONLY
    assert os.statvfs("/workspace").f_flag & os.ST_RDONLY
    with pytest.raises(OSError):
        Path("/prguard-owned").write_text("blocked")
    with pytest.raises(OSError):
        Path("/workspace/prguard-owned").write_text("blocked")


def test_private_runtime_paths_are_writable() -> None:
    for path in (Path.home() / "probe", Path("/tmp/probe")):
        path.write_text("ok")
        assert path.read_text() == "ok"
        path.unlink()


def test_network_namespace_has_no_route() -> None:
    client = socket.socket()
    client.settimeout(0.5)
    try:
        with pytest.raises(OSError):
            client.connect(("1.1.1.1", 53))
    finally:
        client.close()


def test_cgroup_limits() -> None:
    root = Path("/sys/fs/cgroup")
    memory = (root / "memory.max").read_text().strip()
    pids = (root / "pids.max").read_text().strip()
    quota, period = (root / "cpu.max").read_text().split()
    assert memory.isdigit() and int(memory) <= 256 * 1024 * 1024
    assert pids.isdigit() and int(pids) <= 64
    assert quota.isdigit() and int(quota) / int(period) <= 0.5
'''


def _git(repository: Path, *argv: str) -> str:
    completed = subprocess.run(
        ["git", *argv],
        cwd=repository,
        check=True,
        shell=False,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def run_probe(image: str, work_root: Path) -> Path:
    root = work_root.expanduser().resolve() / f"container-probe-{uuid4().hex[:8]}"
    repository = root / "repo"
    tests = repository / "tests"
    tests.mkdir(parents=True)
    (tests / "test_container_boundary.py").write_text(_PROBE_TEST, encoding="utf-8")
    _git(repository, "init", "-q")
    _git(repository, "config", "user.name", "PRGuard Probe")
    _git(repository, "config", "user.email", "prguard-probe@users.noreply.github.com")
    _git(repository, "add", ".")
    _git(repository, "commit", "-q", "-m", "test: add container boundary probe")
    commit = _git(repository, "rev-parse", "HEAD")
    command = ["pytest", "-q", "tests"]
    task = Task(
        case_id="container-security-probe",
        repository=repository,
        base_commit=commit,
        issue="Verify the declared container execution boundary.",
        commands=[CommandSpec(argv=command, kind="pytest", timeout_seconds=30)],
        allowed_commands=[command],
        command_timeout_seconds=30,
        task_timeout_seconds=60,
        container=ContainerExecutionSpec(
            image=image,
            memory_mb=256,
            cpus=0.5,
            pids_limit=64,
        ),
    )
    report = VerificationHarness(root / "artifacts").run(task)
    if report.outcome is not RunOutcome.PASSED:
        detail = report.commands[0].stderr if report.commands else "no command result"
        raise RuntimeError(f"container security probe failed: {report.outcome}: {detail}")
    artifact_directory = Path(report.artifact_directory)
    manifest = artifact_directory / "manifest.json"
    verify_manifest(manifest)
    print("PRGuard container security probe: PASSED")
    print("  non-root + no-new-privileges + zero effective capabilities")
    print("  read-only root/worktree + writable private HOME/TMP")
    print("  no network route + memory/CPU/PID cgroup limits")
    print(f"  image:    {image}")
    print(f"  manifest: {manifest}")
    return artifact_directory


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True, help="full sha256 image ID or digest")
    parser.add_argument("--work-root", type=Path, default=Path("work"))
    args = parser.parse_args()
    run_probe(args.image, args.work_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
