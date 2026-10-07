from __future__ import annotations


class CareerIdentityError(RuntimeError):
    """Base error for Career Identity domain failures."""


class CareerIdentityNotFound(CareerIdentityError):
    def __init__(self, user_id: str) -> None:
        super().__init__(f"career identity not found for user {user_id!r}")
        self.user_id = user_id


class CareerIdentityFactNotFound(CareerIdentityError):
    def __init__(self, fact_id: str) -> None:
        super().__init__(f"career identity fact not found: {fact_id!r}")
        self.fact_id = fact_id


class CareerIdentityVersionConflict(CareerIdentityError):
    def __init__(self, expected_version: int, actual_version: int) -> None:
        super().__init__(
            f"career identity version conflict: expected {expected_version}, got {actual_version}"
        )
        self.expected_version = expected_version
        self.actual_version = actual_version


class CareerIdentityValidationError(CareerIdentityError, ValueError):
    def __init__(self, message: str, *, code: str = "invalid_career_identity") -> None:
        super().__init__(message)
        self.code = code


class CareerIdentityStateTransitionError(CareerIdentityValidationError):
    def __init__(self, current_state: str, target_state: str) -> None:
        super().__init__(
            f"invalid career fact state transition: {current_state!r} -> {target_state!r}",
            code="invalid_fact_state_transition",
        )
        self.current_state = current_state
        self.target_state = target_state

