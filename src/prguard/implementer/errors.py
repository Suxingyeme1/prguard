"""Implementer workflow failures."""


class ImplementerError(RuntimeError):
    """Base class for expected Implementer failures."""


class RepositoryAccessError(ImplementerError):
    """A repository read exceeds the granted capability."""


class PatchPolicyError(ImplementerError):
    """A proposed patch exceeds the task edit policy."""


class ProviderError(ImplementerError):
    """A model provider failed to return a valid proposal."""
