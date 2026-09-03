"""Expected failures while preparing remote tasks."""


class OnboardingError(RuntimeError):
    """An Issue or repository could not become a safe frozen task."""


class GitHubAPIError(OnboardingError):
    """GitHub returned an invalid or unsuccessful response."""


class ProjectDiscoveryError(OnboardingError):
    """A safe executable project policy could not be determined."""
