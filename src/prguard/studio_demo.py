"""Offline review-regression fixture; scripted reasoning, real Git and verification."""

from pathlib import Path

from prguard.demo import _git
from prguard.schemas import CommandSpec, FixTask, ImplementerProposal, ReviewerSubmission

REVIEW_DEMO_ISSUE = (
    "normalize() must accept None as empty text and preserve lowercase normalization."
)
_BASE = "def normalize(value):\n    return value.strip().lower()\n"
_TEST = "from normalizer import normalize\n\ndef test_none():\n    assert normalize(None) == ''\n"


def prepare_review_demo_task(root: Path) -> FixTask:
    repository = root / "repository"
    (repository / "tests").mkdir(parents=True)
    (repository / "normalizer.py").write_text(_BASE, encoding="utf-8")
    (repository / "tests/test_normalizer.py").write_text(_TEST, encoding="utf-8")
    _git(repository, "init", "-b", "main")
    _git(repository, "config", "user.name", "PRGuard Demo")
    _git(repository, "config", "user.email", "demo@prguard.invalid")
    _git(repository, "add", ".")
    _git(repository, "commit", "-m", "review demo base")
    argv = ["pytest", "-q", "tests"]
    return FixTask(
        case_id="studio-demo-review-regression", repository=repository,
        base_commit=_git(repository, "rev-parse", "HEAD"), issue=REVIEW_DEMO_ISSUE,
        commands=[CommandSpec(argv=argv, kind="pytest")], allowed_commands=[argv],
        writable_paths=["*.py", "tests/**"],
        protected_paths=[".git/**", ".github/**", ".env*", "**/*.key"],
        command_timeout_seconds=20, task_timeout_seconds=90, max_repair_attempts=1,
    )


def review_demo_initial() -> list[ImplementerProposal]:
    return [ImplementerProposal.model_validate({
        "plan": ["Accept missing input", "Run the existing None test"],
        "summary": "Handle None, but accidentally remove lowercase conversion.",
        "tests_changed": False,
        "edits": [{
            "operation": "replace_text", "path": "normalizer.py",
            "old_text": "    return value.strip().lower()\n",
            "new_text": "    if value is None:\n        return ''\n    return value.strip()\n",
        }],
    })]


def review_demo_repair() -> list[ImplementerProposal]:
    return [ImplementerProposal.model_validate({
        "plan": ["Restore lowercase behavior", "Add a regression test for existing string inputs"],
        "summary": "Restore lowercase conversion and add the missing regression test.",
        "tests_changed": True,
        "edits": [{
            "operation": "replace_text", "path": "normalizer.py",
            "old_text": "    return value.strip()\n",
            "new_text": "    return value.strip().lower()\n",
        }, {
            "operation": "create_file", "path": "tests/test_regression.py",
            "content": (
                "from normalizer import normalize\n\ndef test_existing_lowercase_behavior():\n"
                "    assert normalize(' HELLO ') == 'hello'\n"
            ),
        }],
    })]


def review_demo_submission() -> ReviewerSubmission:
    return ReviewerSubmission.model_validate({
        "summary": "The existing test passes, but the patch removes lowercase behavior.",
        "findings": [{
            "severity": "P2", "category": "regression", "file": "normalizer.py", "line": 4,
            "symbol": "normalize", "claim": "String inputs are no longer converted to lowercase.",
            "evidence": "The Base return used strip().lower(); the candidate calls only strip().",
            "verification": (
                "normalize(' HELLO ') returns 'HELLO'; existing behavior requires 'hello'."
            ),
            "confidence": 0.99,
        }],
    })
