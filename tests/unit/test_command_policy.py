import sys

import pytest

from prguard.harness.errors import CommandPolicyError
from prguard.harness.policy import CommandPolicy


@pytest.mark.parametrize(
    "argv",
    [
        ["pytest", "-q", "tests"],
        ["python", "-m", "pytest", "-q"],
        ["ruff", "check", "."],
        ["python3.12", "-m", "ruff", "check", "src"],
    ],
)
def test_authorizes_supported_exact_argv(argv: list[str]) -> None:
    effective = CommandPolicy([argv]).authorize(argv)
    assert effective[0] == sys.executable


@pytest.mark.parametrize(
    "argv",
    [
        ["sh", "-c", "pytest"],
        ["python", "-c", "print('x')"],
        ["pytest", "../tests"],
        ["pytest", "-q;touch", "owned"],
        ["/usr/bin/pytest", "-q"],
        ["python", "-m", "http.server"],
    ],
)
def test_rejects_shell_and_escaping_forms(argv: list[str]) -> None:
    with pytest.raises(CommandPolicyError):
        CommandPolicy([argv])


def test_task_allowlist_is_exact() -> None:
    policy = CommandPolicy([["pytest", "-q"]])
    with pytest.raises(CommandPolicyError, match="task allowlist"):
        policy.authorize(["pytest", "-q", "tests"])


def test_container_authorization_uses_declared_bare_python() -> None:
    command = ["pytest", "-q", "tests"]
    policy = CommandPolicy([command])
    assert policy.authorize_container(command, "python3") == [
        "python3",
        "-m",
        "pytest",
        "-q",
        "tests",
    ]
