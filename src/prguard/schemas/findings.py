"""Independent review output contracts."""

from enum import StrEnum

from pydantic import Field, model_validator

from prguard.schemas.common import StrictModel


class Severity(StrEnum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class FindingCategory(StrEnum):
    CORRECTNESS = "correctness"
    REGRESSION = "regression"
    SECURITY = "security"
    API_CONTRACT = "api_contract"
    ERROR_HANDLING = "error_handling"
    MAINTAINABILITY = "maintainability"
    TEST_GAP = "test_gap"
    ENVIRONMENT = "environment"


class ReviewFinding(StrictModel):
    severity: Severity
    category: FindingCategory
    file: str = Field(min_length=1)
    line: int | None = Field(default=None, ge=1)
    symbol: str | None = Field(default=None, min_length=1)
    claim: str = Field(min_length=1, max_length=4000)
    evidence: str = Field(min_length=1, max_length=8000)
    verification: str = Field(min_length=1, max_length=4000)
    confidence: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def relative_file(self) -> "ReviewFinding":
        from pathlib import Path

        path = Path(self.file)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("finding file must be repository-relative")
        return self
