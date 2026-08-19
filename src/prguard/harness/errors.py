"""Typed deterministic harness failures."""


class HarnessError(RuntimeError):
    """Base class for expected harness failures."""


class PreflightError(HarnessError):
    """Repository or input preflight failed."""


class CommandPolicyError(HarnessError):
    """An argv request exceeds the command capability."""


class ArtifactIntegrityError(HarnessError):
    """An artifact manifest or payload failed verification."""
