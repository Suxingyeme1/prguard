from pathlib import Path

import pytest

from prguard.onboarding.errors import OnboardingError
from prguard.onboarding.materialize import materialize_public_checkout
from prguard.schemas import GitHubIssueReference, GitHubIssueSnapshot
from tests.conftest import run_git


def _snapshot(remote: Path, commit: str) -> GitHubIssueSnapshot:
    return GitHubIssueSnapshot(
        reference=GitHubIssueReference(
            owner="acme",
            repository="calc",
            number=1,
            url="https://github.com/acme/calc/issues/1",
        ),
        title="Fix calc",
        state="open",
        repository_url="https://github.com/acme/calc",
        clone_url=str(remote),
        default_branch="main",
        base_commit=commit,
    )


@pytest.mark.integration
def test_materializer_fetches_only_frozen_commit_into_clean_checkout(
    make_repo, tmp_path: Path
) -> None:
    remote, commit = make_repo({"calc.py": "VALUE = 1\n"})

    checkout = materialize_public_checkout(_snapshot(remote, commit), tmp_path / "checkouts")

    assert run_git(checkout, "rev-parse", "HEAD") == commit
    assert run_git(checkout, "status", "--porcelain") == ""
    assert (checkout / "calc.py").read_text() == "VALUE = 1\n"


@pytest.mark.integration
def test_materializer_local_cache_does_not_create_invalid_promisor_remote(
    make_repo, tmp_path: Path
) -> None:
    source, commit = make_repo({"calc.py": "VALUE = 1\n"})
    run_git(source, "remote", "add", "origin", "https://github.com/acme/calc.git")

    checkout = materialize_public_checkout(
        _snapshot(source, commit).model_copy(
            update={"clone_url": "https://github.com/acme/calc.git"}
        ),
        tmp_path / "checkouts",
        source_repository=source,
    )

    config = run_git(checkout, "config", "--local", "--list")
    assert ".promisor=" not in config
    assert ".partialclonefilter=" not in config


@pytest.mark.integration
def test_materializer_removes_owned_partial_checkout_on_failure(tmp_path: Path) -> None:
    snapshot = _snapshot(tmp_path / "missing-remote", "a" * 40)
    root = tmp_path / "checkouts"

    with pytest.raises(OnboardingError, match="Git materialization failed"):
        materialize_public_checkout(snapshot, root)

    assert list(root.iterdir()) == []


@pytest.mark.integration
def test_materializer_rejects_local_cache_with_mismatched_origin(
    make_repo, tmp_path: Path
) -> None:
    source, commit = make_repo({"calc.py": "VALUE = 1\n"})
    run_git(source, "remote", "add", "origin", "https://github.com/other/repo.git")
    snapshot = _snapshot(source, commit).model_copy(
        update={"clone_url": "https://github.com/acme/calc.git"}
    )

    with pytest.raises(OnboardingError, match="origin does not match"):
        materialize_public_checkout(
            snapshot,
            tmp_path / "checkouts",
            source_repository=source,
        )

    assert not (tmp_path / "checkouts").exists()
