"""Read-only monetization catalog and account entitlement routes."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from backend.api.dependencies import CurrentUser, get_current_user, get_session
from backend.api.envelope import (
    VALIDATION_ERROR,
    error_envelope,
    lightweight_success_envelope,
)
from backend.api.monetization_access import (
    blocked_entitlement_response,
    decision_data,
)
from backend.monetization.enforcement import (
    evaluate_account_access,
    increment_feature_usage,
    usage_counter_snapshot,
)
from backend.monetization.entitlements import UsageContext, decide_access
from backend.monetization.features import MonetizationFeatureKey, feature_definitions
from backend.monetization.plans import plan_definitions
from backend.monetization.reports import (
    ReportProductKey,
    report_product_definition,
    report_product_definitions,
)
from backend.monetization.repository import MonetizationRepository
from backend.monetization.resolver import resolve_account_entitlements

router = APIRouter(prefix="/monetization", tags=["monetization"])


@router.get("/plans")
def list_monetization_plans() -> dict:
    return lightweight_success_envelope(
        data={
            "plans": [plan.model_dump(mode="json") for plan in plan_definitions()]
        }
    )


@router.get("/features")
def list_monetization_features() -> dict:
    return lightweight_success_envelope(
        data={
            "features": [
                feature.model_dump(mode="json")
                for feature in feature_definitions()
            ]
        }
    )


@router.get("/reports")
def list_monetization_reports() -> dict:
    return lightweight_success_envelope(
        data={
            "reports": [
                report.model_dump(mode="json")
                for report in report_product_definitions()
            ]
        }
    )


@router.get("/access-preview")
def monetization_access_preview(
    request: Request,
    plan_key: str | None = Query(default=None, min_length=1),
    feature_key: str = Query(..., min_length=1),
    used: int | None = Query(default=None, ge=0),
    session: Session = Depends(get_session),
) -> dict:
    usage_context = UsageContext(used=used) if used is not None else None
    try:
        current = _optional_current_user(request, session)
        if plan_key is not None:
            decision = decide_access(
                plan_key=plan_key,
                feature_key=feature_key,
                usage_context=usage_context,
            )
        elif current is not None:
            decision = evaluate_account_access(
                MonetizationRepository(session),
                user_id=current.user.user_id,
                feature_key=feature_key,
                now=_now(),
            )
        else:
            decision = decide_access(
                plan_key="free",
                feature_key=feature_key,
                usage_context=usage_context,
            )
    except ValueError as exc:
        return JSONResponse(
            status_code=400,
            content=error_envelope(code=VALIDATION_ERROR, message=str(exc)),
        )
    return lightweight_success_envelope(
        data={"decision": decision.model_dump(mode="json")}
    )


@router.get("/me")
def get_my_monetization_account(
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    snapshot = resolve_account_entitlements(
        MonetizationRepository(session),
        user_id=current.user.user_id,
        now=_now(),
    )
    data = snapshot.model_dump(mode="json")
    return lightweight_success_envelope(
        data={
            "account": {
                "monetization_account_id": data["monetization_account_id"],
                "user_id": data["user_id"],
                "account_type": data["account_type"],
                "account_status": data["account_status"],
                "assigned_seats_count": data["assigned_seats_count"],
                "seat_limit": data["seat_limit"],
                "safe_metadata": data["safe_metadata"],
            },
            "entitlements": data,
        }
    )


@router.get("/entitlements")
def get_my_entitlements(
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    snapshot = resolve_account_entitlements(
        MonetizationRepository(session),
        user_id=current.user.user_id,
        now=_now(),
    )
    return lightweight_success_envelope(
        data={"entitlements": snapshot.model_dump(mode="json")}
    )


@router.get("/usage")
def get_my_monetization_usage(
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    repo = MonetizationRepository(session)
    snapshot = resolve_account_entitlements(
        repo,
        user_id=current.user.user_id,
        now=_now(),
    )
    counters = []
    if snapshot.monetization_account_id is not None:
        counters = [
            usage_counter_snapshot(counter).model_dump(mode="json")
            for counter in repo.list_usage_counters(
                monetization_account_id=snapshot.monetization_account_id,
                now=_now(),
            )
        ]
    return lightweight_success_envelope(
        data={
            "plan_key": snapshot.plan_key.value,
            "account_status": snapshot.account_status.value,
            "usage": counters,
        }
    )


@router.post("/reports/{report_key}/generate", response_model=None)
def generate_report_stub(
    report_key: ReportProductKey,
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> JSONResponse | dict:
    repo = MonetizationRepository(session)
    report = report_product_definition(report_key)
    blocked = _blocked_report_feature(
        repo,
        current=current,
        feature_keys=report.paid_full_report_feature_keys,
    )
    if blocked is not None:
        return blocked_entitlement_response(blocked)

    usage_decision = increment_feature_usage(
        repo,
        user_id=current.user.user_id,
        feature_key=MonetizationFeatureKey.FULL_REPORT_GENERATION,
        now=_now(),
    )
    payload = _report_workflow_payload(
        report_key=report.report_key.value,
        workflow="full_report_generation",
        generated_at=_now(),
        access_decision=usage_decision,
        sections=report.included_sections,
        note=(
            "Structured JSON report placeholder only; no PDF or download is "
            "generated in Layer 15 Batch 4."
        ),
    )
    return lightweight_success_envelope(data={"report": payload})


@router.post("/reports/{report_key}/export", response_model=None)
def export_report_stub(
    report_key: ReportProductKey,
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> JSONResponse | dict:
    repo = MonetizationRepository(session)
    report = report_product_definition(report_key)
    if report.export_feature_key is None:
        return JSONResponse(
            status_code=400,
            content=error_envelope(
                code=VALIDATION_ERROR,
                message=f"{report.report_key.value} is not exportable.",
            ),
        )
    repo.ensure_account_for_user(user_id=current.user.user_id)
    access_decision = evaluate_account_access(
        repo,
        user_id=current.user.user_id,
        feature_key=report.export_feature_key,
        now=_now(),
        create_usage_counter=True,
    )
    if not access_decision.allowed:
        return blocked_entitlement_response(access_decision)

    usage_decision = increment_feature_usage(
        repo,
        user_id=current.user.user_id,
        feature_key=report.export_feature_key,
        now=_now(),
    )
    payload = _report_workflow_payload(
        report_key=report.report_key.value,
        workflow="exportable_strategy_plan",
        generated_at=_now(),
        access_decision=usage_decision,
        sections=report.included_sections,
        note=(
            "Structured export placeholder only; no PDF, file download, or "
            "checkout flow is generated in Layer 15 Batch 4."
        ),
    )
    return lightweight_success_envelope(data={"export": payload})


def _optional_current_user(request: Request, session: Session) -> CurrentUser | None:
    try:
        return get_current_user(request, session)
    except HTTPException as exc:
        if exc.status_code == status.HTTP_401_UNAUTHORIZED:
            return None
        raise


def _now() -> datetime:
    return datetime.now(UTC)


def _blocked_report_feature(
    repo: MonetizationRepository,
    *,
    current: CurrentUser,
    feature_keys: tuple[MonetizationFeatureKey, ...],
) -> object | None:
    repo.ensure_account_for_user(user_id=current.user.user_id)
    for feature_key in feature_keys:
        decision = evaluate_account_access(
            repo,
            user_id=current.user.user_id,
            feature_key=feature_key,
            now=_now(),
            create_usage_counter=True,
        )
        if not decision.allowed:
            return decision
    return None


def _report_workflow_payload(
    *,
    report_key: str,
    workflow: str,
    generated_at: datetime,
    access_decision,
    sections: tuple[str, ...],
    note: str,
) -> dict:
    return {
        "report_key": report_key,
        "workflow": workflow,
        "generated_at": generated_at.isoformat(),
        "access_decision": decision_data(access_decision),
        "sections": [
            {
                "section_key": section.replace(" ", "_").replace("-", "_"),
                "title": section,
                "body": (
                    "Product-ready placeholder section. Full rendering and "
                    "file export remain deferred."
                ),
            }
            for section in sections
        ],
        "note": note,
    }
