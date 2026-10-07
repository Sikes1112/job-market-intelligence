"""Layer 36A career decision exceptions."""

from __future__ import annotations


class CareerDecisionNotFound(LookupError):
    pass


class CareerDecisionValidationError(ValueError):
    def __init__(self, message: str, *, code: str = "CAREER_DECISION_VALIDATION_ERROR") -> None:
        super().__init__(message)
        self.code = code


class CareerDecisionTransitionError(CareerDecisionValidationError):
    pass
