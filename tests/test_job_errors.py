import pytest
from pydantic import ValidationError

from backend.orchestration.jobs.errors import (
    RETRYABLE_ERROR_CODES,
    ErrorCode,
    JobError,
    JobWarning,
    WarningSeverity,
    is_retryable,
)

EXPECTED_ERROR_CODES = {
    "INPUT_VALIDATION_ERROR",
    "DEPENDENCY_MISSING",
    "SOURCE_UNAVAILABLE",
    "RATE_LIMITED",
    "PARSE_FAILURE",
    "INTEGRITY_CHECK_FAILED",
    "TIMEOUT",
    "NO_MEANINGFUL_CHANGE",
    "INTERNAL_EXCEPTION",
}


def test_all_documented_error_codes_present() -> None:
    assert ErrorCode.values() == EXPECTED_ERROR_CODES


@pytest.mark.parametrize(
    "code",
    [ErrorCode.SOURCE_UNAVAILABLE, ErrorCode.RATE_LIMITED, ErrorCode.TIMEOUT],
)
def test_retryable_codes_match_spec(code: ErrorCode) -> None:
    assert code in RETRYABLE_ERROR_CODES
    assert is_retryable(code) is True
    assert is_retryable(code.value) is True


@pytest.mark.parametrize(
    "code",
    [
        ErrorCode.INPUT_VALIDATION_ERROR,
        ErrorCode.DEPENDENCY_MISSING,
        ErrorCode.INTEGRITY_CHECK_FAILED,
        ErrorCode.NO_MEANINGFUL_CHANGE,
        # PARSE_FAILURE and INTERNAL_EXCEPTION are "sometimes" — kept out of
        # the auto-retry set so callers must opt in.
        ErrorCode.PARSE_FAILURE,
        ErrorCode.INTERNAL_EXCEPTION,
    ],
)
def test_non_retryable_codes(code: ErrorCode) -> None:
    assert code not in RETRYABLE_ERROR_CODES
    assert is_retryable(code) is False


def test_is_retryable_rejects_unknown_string() -> None:
    with pytest.raises(ValueError):
        is_retryable("NOT_A_CODE")


def test_job_error_serializes_minimal_form() -> None:
    err = JobError(error_code=ErrorCode.DEPENDENCY_MISSING, error_message="missing presence_v33")
    dumped = err.model_dump()
    assert dumped == {
        "error_code": "DEPENDENCY_MISSING",
        "error_message": "missing presence_v33",
        "error_details": None,
    }


def test_job_error_round_trip_with_details() -> None:
    payload = {
        "error_code": "DEPENDENCY_MISSING",
        "error_message": "missing presence_v33",
        "error_details": {"missing_dependency": "presence_v33"},
    }
    err = JobError.model_validate(payload)
    assert err.error_details == {"missing_dependency": "presence_v33"}
    assert err.model_dump() == payload


def test_job_error_rejects_blank_message() -> None:
    with pytest.raises(ValidationError):
        JobError(error_code=ErrorCode.TIMEOUT, error_message="")


def test_job_error_rejects_unknown_code() -> None:
    with pytest.raises(ValidationError):
        JobError.model_validate({"error_code": "NOPE", "error_message": "x"})


def test_job_warning_round_trip() -> None:
    warn = JobWarning(
        warning_code="LOW_CONFIDENCE_ENTRY_LEVEL",
        severity=WarningSeverity.LOW,
        scope_type="company_region_pair",
        scope_ref="comp_101::greater_boston",
        message="Reduced confidence due to incomplete role metadata.",
    )
    dumped = warn.model_dump()
    assert dumped["severity"] == "low"
    assert dumped["scope_ref"] == "comp_101::greater_boston"


def test_job_warning_extra_fields_forbidden() -> None:
    with pytest.raises(ValidationError):
        JobWarning.model_validate(
            {
                "warning_code": "X",
                "severity": "low",
                "message": "m",
                "extra": "no",
            }
        )


def test_job_warning_severity_must_be_known() -> None:
    with pytest.raises(ValidationError):
        JobWarning(warning_code="X", severity="critical", message="m")  # type: ignore[arg-type]
