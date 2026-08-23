import json
from urllib.error import HTTPError

import pytest

from prguard.onboarding.errors import GitHubAPIError
from prguard.onboarding.github import GitHubClient, parse_github_issue_url


class FakeResponse:
    def __init__(self, payload: object) -> None:
        self.payload = json.dumps(payload).encode()

    def read(self, amount: int = -1) -> bytes:
        return self.payload[:amount] if amount >= 0 else self.payload

    def __enter__(self):
        return self

    def __exit__(self, *args: object) -> None:
        return None


class FakeOpener:
    def __init__(self, responses: list[object]) -> None:
        self.responses = list(responses)
        self.requests = []

    def open(self, request, timeout: float):
        self.requests.append((request, timeout))
        value = self.responses.pop(0)
        if isinstance(value, Exception):
            raise value
        return FakeResponse(value)


def test_parse_github_issue_url_is_canonical_and_bounded() -> None:
    value = parse_github_issue_url("https://github.com/python-humanize/humanize/issues/366")
    assert value.owner == "python-humanize"
    assert value.repository == "humanize"
    assert value.number == 366

    for unsafe in (
        "http://github.com/a/b/issues/1",
        "https://evil.example/a/b/issues/1",
        "https://user:secret@github.com/a/b/issues/1",
        "https://github.com/a/b/pull/1",
        "https://github.com/a/b/issues/1?token=secret",
    ):
        with pytest.raises(GitHubAPIError):
            parse_github_issue_url(unsafe)


def test_client_freezes_issue_repository_and_default_branch_commit() -> None:
    opener = FakeOpener(
        [
            {"title": "Fix zero", "body": "Details", "state": "open"},
            {"default_branch": "main", "private": False, "archived": False},
            {"sha": "a" * 40},
        ]
    )
    client = GitHubClient(token="secret-token", opener=opener)
    snapshot = client.fetch_issue(
        parse_github_issue_url("https://github.com/acme/orders/issues/7")
    )

    assert snapshot.base_commit == "a" * 40
    assert snapshot.clone_url == "https://github.com/acme/orders.git"
    assert snapshot.issue_text == "GitHub Issue #7: Fix zero\n\nDetails"
    assert all(
        request.headers["Authorization"] == "Bearer secret-token"
        for request, _ in opener.requests
    )


def test_client_rejects_pull_request_and_private_repository() -> None:
    pull_client = GitHubClient(
        opener=FakeOpener(
            [{"title": "PR", "body": "", "state": "open", "pull_request": {}}]
        )
    )
    reference = parse_github_issue_url("https://github.com/acme/orders/issues/7")
    with pytest.raises(GitHubAPIError, match="Pull Request"):
        pull_client.fetch_issue(reference)

    private_client = GitHubClient(
        opener=FakeOpener(
            [
                {"title": "Issue", "body": "", "state": "open"},
                {"default_branch": "main", "private": True},
            ]
        )
    )
    with pytest.raises(GitHubAPIError, match="private"):
        private_client.fetch_issue(reference)


def test_client_redacts_token_from_transport_error() -> None:
    error = HTTPError("https://api.github.com", 401, "secret-token", {}, None)
    client = GitHubClient(token="secret-token", retry_count=0, opener=FakeOpener([error]))
    with pytest.raises(GitHubAPIError) as caught:
        client.fetch_issue(parse_github_issue_url("https://github.com/a/b/issues/1"))
    assert "secret-token" not in str(caught.value)
