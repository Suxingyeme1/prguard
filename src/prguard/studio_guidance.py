"""Stable, non-authoritative Studio recovery categories; never execute suggested actions."""

from prguard.harness.errors import ArtifactIntegrityError, PreflightError
from prguard.onboarding.errors import ProjectDiscoveryError

_CODES = frozenset({
    "repository_missing", "repository_not_git", "repository_root", "base_unresolved",
    "repository_dirty", "repository_check_failed", "policy_invalid", "policy_conflict",
    "verification_missing", "write_scope_missing",
})


def recovery_code(error: Exception) -> str:
    """Use typed causes, not repository-controlled exception text, to select UI guidance."""

    current: BaseException | None = error
    code = "unexpected_error"
    seen: set[int] = set()
    while current is not None and id(current) not in seen and len(seen) < 8:
        seen.add(id(current))
        if isinstance(current, ArtifactIntegrityError):
            code = "artifact_integrity"
        elif (
            isinstance(current, (PreflightError, ProjectDiscoveryError)) and current.code in _CODES
        ):
            code = current.code
        current = current.__cause__
    return code
