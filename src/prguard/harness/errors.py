"""Typed deterministic harness failures."""


class HarnessError(RuntimeError):
    """Base class for expected harness failures."""


class PreflightError(HarnessError):
    """Repository or input preflight failed."""

    def __init__(self, message: str, *, code: str = "repository_check_failed") -> None:
        super().__init__(message)
        self.code = code


class CommandPolicyError(HarnessError):
    """An argv request exceeds the command capability."""


class ArtifactIntegrityError(HarnessError):
    """An artifact manifest or payload failed verification."""
