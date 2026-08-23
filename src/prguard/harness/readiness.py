"""Deterministic commands that prove a Base Commit is ready for an Agent stage."""

from __future__ import annotations

from prguard.schemas import CommandSpec, HarnessReport


def _is_pytest(command: CommandSpec) -> bool:
    argv = command.argv
    return argv[0] == "pytest" or (
        len(argv) >= 3
        and argv[0] in {"python", "python3", "python3.12"}
        and argv[1:3] == ["-m", "pytest"]
    )


def readiness_commands(commands: list[CommandSpec]) -> list[CommandSpec]:
    """Collect pytest without assertions and execute non-pytest Base gates unchanged."""

    results: list[CommandSpec] = []
    for command in commands:
        argv = list(command.argv)
        if _is_pytest(command):
            insertion = 1 if argv[0] == "pytest" else 3
            if "--collect-only" not in argv and "--co" not in argv:
                argv.insert(insertion, "--collect-only")
            results.append(CommandSpec(argv=argv, kind="pytest_collection"))
        else:
            results.append(CommandSpec(argv=argv, kind=f"base_{command.kind}"))
    return results


def readiness_failure_boundary(report: HarnessReport) -> str:
    failed_collection = any(
        result.kind == "pytest_collection" and not result.passed
        for result in report.commands
    )
    return "base pytest collection" if failed_collection else "base non-pytest gate"
