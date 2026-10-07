"""Layer 40A product measurement, beta, support, and entitlement routes."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from backend.api.dependencies import (
    CurrentAdmin,
    CurrentUser,
    get_current_user,
    get_session,
    require_admin_mutation_access,
    require_admin_read_access,
)
from backend.api.envelope import NOT_FOUND, VALIDATION_ERROR, error_envelope, lightweight_success_envelope
from backend.product_measurement.repository import ProductMeasurementRepository
from backend.product_measurement.schemas import (
    CohortCreate,
    CohortMembershipCreate,
    CommercialExperimentSignalCreate,
    DecisionReflectionCreate,
    EntitlementGrantCreate,
    ExperimentAssignmentCreate,
    FeatureGateCreate,
    ProductEventCreate,
    RecommendationFeedbackCreate,
    StrategyChangeCreate,
    SupportCaseCreate,
    SupportCaseStatus,
    SupportCaseType,
    SupportCaseUpdate,
)
from backend.product_measurement.service import (
    ProductMeasurementNotFound,
    ProductMeasurementService,
    ProductMeasurementValidationError,
    cohort_view,
    commercial_signal_view,
    decision_reflection_view,
    entitlement_grant_view,
    experiment_assignment_view,
    feature_gate_view,
    membership_view,
    product_event_view,
    recommendation_feedback_view,
    strategy_change_view,
    support_case_view,
)
from backend.users.exceptions import CrossUserAccessBlocked, UserNotFound

router = APIRouter(tags=["product-measurement"])


def _service(session: Session) -> ProductMeasurementService:
    return ProductMeasurementService(session)


@router.post("/me/product-events", status_code=status.HTTP_201_CREATED, response_model=None)
def record_product_event(
    request: ProductEventCreate,
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Any:
    try:
        row = _service(session).record_event(current.user.user_id, request)
    except (ProductMeasurementNotFound, CrossUserAccessBlocked):
        return _not_found("Referenced product event resource not found.")
    except (ProductMeasurementValidationError, ValueError) as exc:
        return _validation(str(exc))
    return lightweight_success_envelope(data={"event": product_event_view(row).model_dump(mode="json")})


@router.post("/me/recommendation-feedback", status_code=status.HTTP_201_CREATED, response_model=None)
def submit_recommendation_feedback(
    request: RecommendationFeedbackCreate,
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Any:
    try:
        row = _service(session).submit_recommendation_feedback(current.user.user_id, request)
    except (ProductMeasurementNotFound, CrossUserAccessBlocked):
        return _not_found("Recommendation not found.")
    except ProductMeasurementValidationError as exc:
        return _validation(str(exc))
    return lightweight_success_envelope(
        data={"feedback": recommendation_feedback_view(row).model_dump(mode="json")}
    )


@router.get("/me/recommendation-feedback", response_model=None)
def list_my_recommendation_feedback(
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    rows = _service(session).list_my_feedback(current.user.user_id)
    return lightweight_success_envelope(
        data={"feedback": [recommendation_feedback_view(row).model_dump(mode="json") for row in rows]}
    )


@router.post("/me/decision-reflections", status_code=status.HTTP_201_CREATED, response_model=None)
def record_decision_reflection(
    request: DecisionReflectionCreate,
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Any:
    try:
        row = _service(session).record_reflection(current.user.user_id, request)
    except (ProductMeasurementNotFound, CrossUserAccessBlocked):
        return _not_found("Decision, recommendation, or outcome not found.")
    return lightweight_success_envelope(
        data={"reflection": decision_reflection_view(row).model_dump(mode="json")}
    )


@router.post("/me/strategy-changes", status_code=status.HTTP_201_CREATED, response_model=None)
def record_strategy_change(
    request: StrategyChangeCreate,
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Any:
    try:
        row = _service(session).record_strategy_change(current.user.user_id, request)
    except (ProductMeasurementNotFound, CrossUserAccessBlocked):
        return _not_found("Decision or recommendation not found.")
    return lightweight_success_envelope(
        data={"strategy_change": strategy_change_view(row).model_dump(mode="json")}
    )


@router.get("/me/beta-access", response_model=None)
def get_my_beta_access(
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    return lightweight_success_envelope(
        data=_service(session).beta_access_summary(current.user.user_id)
    )


@router.get("/me/feature-access/{feature_key}", response_model=None)
def get_my_feature_access(
    feature_key: str,
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    decision = _service(session).decide_feature_access(current.user.user_id, feature_key)
    return lightweight_success_envelope(data={"decision": decision.model_dump(mode="json")})


@router.post("/me/support-cases", status_code=status.HTTP_201_CREATED, response_model=None)
def create_support_case(
    request: SupportCaseCreate,
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Any:
    try:
        row = _service(session).create_support_case(current.user.user_id, request)
    except (ProductMeasurementNotFound, CrossUserAccessBlocked):
        return _not_found("Referenced support-case resource not found.")
    return lightweight_success_envelope(data={"support_case": support_case_view(row).model_dump(mode="json")})


@router.get("/me/support-cases", response_model=None)
def list_my_support_cases(
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    rows = _service(session).list_support_cases(current.user.user_id)
    return lightweight_success_envelope(
        data={"support_cases": [support_case_view(row).model_dump(mode="json") for row in rows]}
    )


@router.post("/me/commercial-signals", status_code=status.HTTP_201_CREATED, response_model=None)
def record_commercial_signal(
    request: CommercialExperimentSignalCreate,
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Any:
    row = _service(session).record_commercial_signal(current.user.user_id, request)
    return lightweight_success_envelope(
        data={"signal": commercial_signal_view(row).model_dump(mode="json")}
    )


@router.get("/admin/beta/cohorts", response_model=None)
def list_beta_cohorts(
    _admin: CurrentAdmin = Depends(require_admin_read_access),
    session: Session = Depends(get_session),
) -> dict:
    rows = _service(session).list_cohorts()
    return lightweight_success_envelope(
        data={"cohorts": [cohort_view(row).model_dump(mode="json") for row in rows]}
    )


@router.post("/admin/beta/cohorts", response_model=None)
def upsert_beta_cohort(
    request: CohortCreate,
    admin: CurrentAdmin = Depends(require_admin_mutation_access),
    session: Session = Depends(get_session),
) -> dict:
    row = _service(session).upsert_cohort(
        request,
        actor_user_id=admin.current.user.user_id,
        role=admin.role,
    )
    return lightweight_success_envelope(data={"cohort": cohort_view(row).model_dump(mode="json")})


@router.post("/admin/beta/memberships", response_model=None)
def assign_beta_membership(
    request: CohortMembershipCreate,
    admin: CurrentAdmin = Depends(require_admin_mutation_access),
    session: Session = Depends(get_session),
) -> Any:
    try:
        row = _service(session).assign_cohort_membership(
            request,
            actor_user_id=admin.current.user.user_id,
            role=admin.role,
        )
    except (ProductMeasurementNotFound, UserNotFound):
        return _not_found("User or cohort not found.")
    return lightweight_success_envelope(
        data={"membership": membership_view(row, cohort_key=request.cohort_key).model_dump(mode="json")}
    )


@router.get("/admin/feature-gates", response_model=None)
def list_feature_gates(
    _admin: CurrentAdmin = Depends(require_admin_read_access),
    session: Session = Depends(get_session),
) -> dict:
    rows = _service(session).list_feature_gates()
    return lightweight_success_envelope(
        data={"feature_gates": [feature_gate_view(row).model_dump(mode="json") for row in rows]}
    )


@router.post("/admin/feature-gates", response_model=None)
def upsert_feature_gate(
    request: FeatureGateCreate,
    admin: CurrentAdmin = Depends(require_admin_mutation_access),
    session: Session = Depends(get_session),
) -> dict:
    row = _service(session).upsert_feature_gate(
        request,
        actor_user_id=admin.current.user.user_id,
        role=admin.role,
    )
    return lightweight_success_envelope(
        data={"feature_gate": feature_gate_view(row).model_dump(mode="json")}
    )


@router.post("/admin/experiment-assignments", response_model=None)
def assign_experiment(
    request: ExperimentAssignmentCreate,
    admin: CurrentAdmin = Depends(require_admin_mutation_access),
    session: Session = Depends(get_session),
) -> Any:
    try:
        row = _service(session).assign_experiment(
            request,
            actor_user_id=admin.current.user.user_id,
            role=admin.role,
        )
    except UserNotFound:
        return _not_found("User not found.")
    return lightweight_success_envelope(
        data={"assignment": experiment_assignment_view(row, cohort_key=request.cohort_key).model_dump(mode="json")}
    )


@router.post("/admin/product-entitlements", response_model=None)
def grant_product_entitlement(
    request: EntitlementGrantCreate,
    admin: CurrentAdmin = Depends(require_admin_mutation_access),
    session: Session = Depends(get_session),
) -> Any:
    try:
        row = _service(session).create_entitlement_grant(
            request,
            actor_user_id=admin.current.user.user_id,
            role=admin.role,
        )
    except UserNotFound:
        return _not_found("User not found.")
    return lightweight_success_envelope(
        data={"entitlement": entitlement_grant_view(row).model_dump(mode="json")}
    )


@router.get("/admin/support-cases", response_model=None)
def admin_list_support_cases(
    status_filter: SupportCaseStatus | None = Query(default=None, alias="status"),
    case_type: SupportCaseType | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    _admin: CurrentAdmin = Depends(require_admin_read_access),
    session: Session = Depends(get_session),
) -> dict:
    rows = _service(session).admin_list_support_cases(
        status=status_filter,
        case_type=case_type,
        limit=limit,
    )
    return lightweight_success_envelope(
        data={"support_cases": [support_case_view(row).model_dump(mode="json") for row in rows]}
    )


@router.patch("/admin/support-cases/{support_case_id}", response_model=None)
def admin_update_support_case(
    support_case_id: str,
    request: SupportCaseUpdate,
    admin: CurrentAdmin = Depends(require_admin_mutation_access),
    session: Session = Depends(get_session),
) -> Any:
    try:
        row = _service(session).update_support_case(
            support_case_id,
            request,
            actor_user_id=admin.current.user.user_id,
            role=admin.role,
        )
    except ProductMeasurementNotFound:
        return _not_found("Support case not found.")
    return lightweight_success_envelope(data={"support_case": support_case_view(row).model_dump(mode="json")})


@router.get("/admin/beta/analytics", response_model=None)
def admin_beta_analytics(
    cohort_key: str | None = Query(default=None, min_length=1, max_length=64),
    since: datetime | None = Query(default=None),
    until: datetime | None = Query(default=None),
    _admin: CurrentAdmin = Depends(require_admin_read_access),
    session: Session = Depends(get_session),
) -> dict:
    summary = _service(session).beta_analytics_summary(
        cohort_key=cohort_key,
        since=since,
        until=until,
    )
    return lightweight_success_envelope(data={"analytics": summary.model_dump(mode="json")})


@router.get("/admin/product-events", response_model=None)
def admin_list_product_events(
    user_id: str | None = Query(default=None, min_length=1, max_length=64),
    cohort_key: str | None = Query(default=None, min_length=1, max_length=64),
    event_type: str | None = Query(default=None, min_length=1, max_length=64),
    limit: int = Query(default=100, ge=1, le=500),
    _admin: CurrentAdmin = Depends(require_admin_read_access),
    session: Session = Depends(get_session),
) -> dict:
    rows = ProductMeasurementRepository(session).list_events(
        user_id=user_id,
        cohort_key=cohort_key,
        event_type=event_type,
        limit=limit,
    )
    return lightweight_success_envelope(
        data={"events": [product_event_view(row).model_dump(mode="json") for row in rows]}
    )


def _not_found(message: str) -> JSONResponse:
    return JSONResponse(status_code=404, content=error_envelope(code=NOT_FOUND, message=message))


def _validation(message: str) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=error_envelope(code=VALIDATION_ERROR, message=message),
    )
