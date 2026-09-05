"""Implementer workflow failures."""

from __future__ import annotations

from typing import Any


class ImplementerError(RuntimeError):
    """Base class for expected Implementer failures."""


class RepositoryAccessError(ImplementerError):
    """A repository read exceeds the granted capability."""


class PatchPolicyError(ImplementerError):
    """A proposed patch exceeds the task edit policy."""


class EditConflictError(PatchPolicyError):
    """A bounded structured edit no longer identifies exactly the inspected source."""


class ProviderError(ImplementerError):
    """A model provider failed to return a valid proposal."""

    def __init__(self, message: str, *, evidence: Any | None = None) -> None:
        super().__init__(message)
        self.evidence = evidence
