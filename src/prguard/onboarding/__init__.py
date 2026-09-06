"""Turn remote Issues and repository policy into frozen PRGuard tasks."""

from prguard.onboarding.github import GitHubClient, parse_github_issue_url
from prguard.onboarding.local import prepare_local_issue, read_issue_file
from prguard.onboarding.prepare import prepare_github_issue
from prguard.onboarding.profile import (
    discover_project_policy,
    inspect_project_policy,
    load_operator_project_config,
    load_project_config,
    render_project_config,
)

__all__ = [
    "GitHubClient",
    "discover_project_policy",
    "inspect_project_policy",
    "load_operator_project_config",
    "load_project_config",
    "parse_github_issue_url",
    "prepare_github_issue",
    "prepare_local_issue",
    "read_issue_file",
    "render_project_config",
]
