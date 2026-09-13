import pytest

from prguard.harness.errors import ArtifactIntegrityError, PreflightError
from prguard.onboarding.errors import OnboardingError, ProjectDiscoveryError
from prguard.studio_guidance import recovery_code


@pytest.mark.parametrize("error,expected", [
    (PreflightError("opaque", code="repository_dirty"), "repository_dirty"),
    (ProjectDiscoveryError("opaque", code="verification_missing"), "verification_missing"),
    (ArtifactIntegrityError("changed"), "artifact_integrity"),
    (ValueError("source repository must be clean before creating a worktree"), "unexpected_error"),
    (PreflightError("opaque", code="untrusted-code"), "unexpected_error"),
])
def test_guidance_uses_typed_codes_not_error_text(error, expected):
    assert recovery_code(error) == expected


def test_guidance_follows_wrapped_causes_and_handles_cycles():
    error = OnboardingError("preflight failed")
    cause = PreflightError("opaque", code="base_unresolved")
    error.__cause__ = cause
    cause.__cause__ = error
    assert recovery_code(error) == "base_unresolved"
