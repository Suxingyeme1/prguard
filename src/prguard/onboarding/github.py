"""Bounded, read-only GitHub REST adapter for public Issue onboarding."""

from __future__ import annotations

import json
import os
import re
import time
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import HTTPRedirectHandler, OpenerDirector, Request, build_opener

from prguard.onboarding.errors import GitHubAPIError
from prguard.schemas import GitHubIssueReference, GitHubIssueSnapshot

_API_ROOT = "https://api.github.com"
_API_VERSION = "2026-03-10"
_MAX_RESPONSE_BYTES = 2_000_000


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class _OpenResponse(Protocol):
    def read(self, amount: int = -1) -> bytes: ...
    def __enter__(self) -> _OpenResponse: ...
    def __exit__(self, *args: object) -> None: ...


def parse_github_issue_url(value: str) -> GitHubIssueReference:
    parsed = urlsplit(value)
    if parsed.scheme != "https" or parsed.hostname != "github.com":
        raise GitHubAPIError("Issue URL must use https://github.com")
    if parsed.username or parsed.password or parsed.port or parsed.query or parsed.fragment:
        raise GitHubAPIError("Issue URL must not contain credentials, port, query, or fragment")
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) != 4 or parts[2] != "issues" or not parts[3].isdigit():
        raise GitHubAPIError("Issue URL must match /OWNER/REPOSITORY/issues/NUMBER")
    owner, raw_repository = parts[:2]
    repository = raw_repository.removesuffix(".git")
    canonical = f"https://github.com/{owner}/{repository}/issues/{int(parts[3])}"
    try:
        return GitHubIssueReference(
            owner=owner,
            repository=repository,
            number=int(parts[3]),
            url=canonical,
        )
    except ValueError as exc:
        raise GitHubAPIError(f"invalid GitHub Issue URL: {exc}") from exc


class GitHubClient:
    def __init__(
        self,
        *,
        token: str | None = None,
        timeout_seconds: float = 20,
        retry_count: int = 2,
        opener: OpenerDirector | Any | None = None,
    ) -> None:
        self._token = token if token is not None else os.environ.get("GITHUB_TOKEN")
        self.timeout_seconds = timeout_seconds
        self.retry_count = retry_count
        self.opener = opener or build_opener(_NoRedirect())

    def _request_json(self, path: str) -> dict[str, Any]:
        if not path.startswith("/") or ".." in path:
            raise GitHubAPIError("unsafe GitHub API path")
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "prguard-onboarding",
            "X-GitHub-Api-Version": _API_VERSION,
        }
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        request = Request(f"{_API_ROOT}{path}", headers=headers, method="GET")
        payload = b""
        for attempt in range(self.retry_count + 1):
            try:
                with self.opener.open(request, timeout=self.timeout_seconds) as response:
                    payload = response.read(_MAX_RESPONSE_BYTES + 1)
                break
            except HTTPError as exc:
                raise GitHubAPIError(f"GitHub API returned HTTP {exc.code}") from exc
            except (URLError, TimeoutError, OSError) as exc:
                if attempt >= self.retry_count:
                    detail = str(exc)
                    if self._token:
                        detail = detail.replace(self._token, "[REDACTED]")
                    raise GitHubAPIError(f"GitHub API request failed: {detail}") from exc
                time.sleep(0.25 * (attempt + 1))
        if len(payload) > _MAX_RESPONSE_BYTES:
            raise GitHubAPIError("GitHub API response exceeds the byte limit")
        try:
            value = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise GitHubAPIError("GitHub API returned invalid JSON") from exc
        if not isinstance(value, dict):
            raise GitHubAPIError("GitHub API response must be an object")
        return value

    def fetch_issue(
        self,
        reference: GitHubIssueReference,
        *,
        base_commit: str | None = None,
    ) -> GitHubIssueSnapshot:
        if base_commit is not None and re.fullmatch(r"[0-9a-fA-F]{7,40}", base_commit) is None:
            raise GitHubAPIError("explicit Base Commit must be a 7-to-40 digit hexadecimal SHA")
        owner = quote(reference.owner, safe="")
        repository = quote(reference.repository, safe="")
        issue = self._request_json(
            f"/repos/{owner}/{repository}/issues/{reference.number}"
        )
        if "pull_request" in issue:
            raise GitHubAPIError("URL identifies a Pull Request; use the review entry instead")
        repo = self._request_json(f"/repos/{owner}/{repository}")
        if bool(repo.get("private")):
            raise GitHubAPIError("private repository onboarding is not supported by this release")
        default_branch = repo.get("default_branch")
        if not isinstance(default_branch, str) or not default_branch:
            raise GitHubAPIError("repository response has no default branch")
        commit_ref = base_commit or default_branch
        commit = self._request_json(
            f"/repos/{owner}/{repository}/commits/{quote(commit_ref, safe='')}"
        )
        sha = commit.get("sha")
        title = issue.get("title")
        body = issue.get("body") or ""
        state = issue.get("state")
        if not isinstance(title, str) or not title.strip():
            raise GitHubAPIError("Issue response has no title")
        if not isinstance(body, str):
            raise GitHubAPIError("Issue body must be text")
        if state not in {"open", "closed"}:
            raise GitHubAPIError("Issue response has an invalid state")
        if not isinstance(sha, str) or len(sha) != 40:
            raise GitHubAPIError("commit response has no full SHA")
        canonical_repo = f"https://github.com/{reference.owner}/{reference.repository}"
        return GitHubIssueSnapshot(
            reference=reference,
            title=title.strip(),
            body=body[:48_000],
            state=state,
            repository_url=canonical_repo,
            clone_url=f"{canonical_repo}.git",
            default_branch=default_branch,
            base_commit=sha.lower(),
            private=False,
            archived=bool(repo.get("archived")),
        )
