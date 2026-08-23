"""Implementer workflow failures."""

from __future__ import annotations

from typing import Any


class ImplementerError(RuntimeError):
    """Base class for expected Implementer failures."""


class RepositoryAccessError(ImplementerError):
    """A repository read exceeds the granted capability."""


class PatchPolicyError(ImplementerError):
    """A proposed patch exceeds the task edit policy."""


class ProviderError(ImplementerError):
    """A model provider failed to return a valid proposal."""

    def __init__(self, message: str, *, evidence: Any | None = None) -> None:
        super().__init__(message)
        self.evidence = evidence
