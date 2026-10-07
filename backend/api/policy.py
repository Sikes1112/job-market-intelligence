"""Read-only Layer 24A policy intelligence API routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.api.dependencies import get_session
from backend.api.envelope import NOT_FOUND, error_envelope, lightweight_success_envelope
from backend.api.geographic_identity import require_canonical_region_id
from backend.geography.exceptions import GeographicResolutionError
from backend.policy import PolicyIntelligenceService, PolicyRegionNotFound
from backend.policy.public_reports import (
    LAYER24_EARLY_CAREER_REPORT_ID,
    build_early_career_opportunity_report,
)
from backend.shared.confidence import Confidence
from backend.shared.freshness import FreshnessStatus

router = APIRouter(prefix="/policy", tags=["policy"])


@router.get("/regions/{region_id}/workforce-dashboard")
def get_workforce_dashboard(
    region_id: str,
    session: Session = Depends(get_session),
) -> dict:
    service = PolicyIntelligenceService(session)
    try:
        region_id = require_canonical_region_id(session, region_id)
        payload = service.build_workforce_dashboard(region_id)
    except (GeographicResolutionError, PolicyRegionNotFound):
        return JSONResponse(
            status_code=404,
            content=error_envelope(
                code=NOT_FOUND,
                message=f"Region not found: {region_id!r}",
            ),
        )
    return _policy_envelope(payload)


@router.get("/regions/{region_id}/early-career-access")
def get_early_career_access(
    region_id: str,
    session: Session = Depends(get_session),
) -> dict:
    service = PolicyIntelligenceService(session)
    try:
        region_id = require_canonical_region_id(session, region_id)
        payload = service.build_early_career_access(region_id)
    except (GeographicResolutionError, PolicyRegionNotFound):
        return JSONResponse(
            status_code=404,
            content=error_envelope(
                code=NOT_FOUND,
                message=f"Region not found: {region_id!r}",
            ),
        )
    return _policy_envelope(payload)


@router.get("/regions/{region_id}/employer-concentration")
def get_employer_concentration(
    region_id: str,
    session: Session = Depends(get_session),
) -> dict:
    service = PolicyIntelligenceService(session)
    try:
        region_id = require_canonical_region_id(session, region_id)
        payload = service.build_employer_concentration(region_id)
    except (GeographicResolutionError, PolicyRegionNotFound):
        return JSONResponse(
            status_code=404,
            content=error_envelope(
                code=NOT_FOUND,
                message=f"Region not found: {region_id!r}",
            ),
        )
    return _policy_envelope(payload)


@router.get("/regions/{region_id}/economic-development")
def get_economic_development(
    region_id: str,
    session: Session = Depends(get_session),
) -> dict:
    service = PolicyIntelligenceService(session)
    try:
        region_id = require_canonical_region_id(session, region_id)
        payload = service.build_economic_development_profile(region_id)
    except (GeographicResolutionError, PolicyRegionNotFound):
        return JSONResponse(
            status_code=404,
            content=error_envelope(
                code=NOT_FOUND,
                message=f"Region not found: {region_id!r}",
            ),
        )
    return _policy_envelope(payload)


@router.get("/regions/{region_id}/peer-comparison")
def get_peer_comparison(
    region_id: str,
    session: Session = Depends(get_session),
) -> dict:
    service = PolicyIntelligenceService(session)
    try:
        region_id = require_canonical_region_id(session, region_id)
        payload = service.build_peer_comparison_profile(region_id)
    except (GeographicResolutionError, PolicyRegionNotFound):
        return JSONResponse(
            status_code=404,
            content=error_envelope(
                code=NOT_FOUND,
                message=f"Region not found: {region_id!r}",
            ),
        )
    return _policy_envelope(payload)


@router.get("/regions/{region_id}/education-alignment")
def get_education_alignment(
    region_id: str,
    session: Session = Depends(get_session),
) -> dict:
    service = PolicyIntelligenceService(session)
    try:
        region_id = require_canonical_region_id(session, region_id)
        payload = service.build_education_alignment_profile(region_id)
    except (GeographicResolutionError, PolicyRegionNotFound):
        return JSONResponse(
            status_code=404,
            content=error_envelope(
                code=NOT_FOUND,
                message=f"Region not found: {region_id!r}",
            ),
        )
    return _policy_envelope(payload)


@router.get("/regions/{region_id}/reports/{report_id}")
def get_policy_report(
    region_id: str,
    report_id: str,
    session: Session = Depends(get_session),
) -> dict:
    if report_id != LAYER24_EARLY_CAREER_REPORT_ID:
        return JSONResponse(
            status_code=404,
            content=error_envelope(
                code=NOT_FOUND,
                message=f"Layer 24 policy report not found: {report_id!r}",
            ),
        )
    service = PolicyIntelligenceService(session)
    try:
        region_id = require_canonical_region_id(session, region_id)
        dashboard = service.build_workforce_dashboard(region_id)
    except (GeographicResolutionError, PolicyRegionNotFound):
        return JSONResponse(
            status_code=404,
            content=error_envelope(
                code=NOT_FOUND,
                message=f"Region not found: {region_id!r}",
            ),
        )
    return _policy_report_envelope(build_early_career_opportunity_report(dashboard))


def _policy_envelope(payload: BaseModel) -> dict[str, Any]:
    data = payload.model_dump(mode="json")
    state = _state_for_payload(payload)
    envelope = lightweight_success_envelope(data=data, state=state)
    envelope["status"] = "partial" if state in {"partial", "stale"} else "success"
    envelope["metadata"].update(
        {
            "freshness": data["freshness"],
            "confidence": data["confidence"],
            "warnings": data["warnings"],
            "source_summary": data["source_summary"],
            "public_safe": data["public_safe"],
        }
    )
    if "limitations" in data:
        envelope["metadata"]["limitations"] = data["limitations"]
    return envelope


def _policy_report_envelope(payload: BaseModel) -> dict[str, Any]:
    data = payload.model_dump(mode="json")
    confidence = data["confidence"]
    freshness_status = data["freshness_status"]
    state = (
        "stale"
        if freshness_status == "stale"
        else ("partial" if confidence in {"low", "unknown"} else "fresh")
    )
    envelope = lightweight_success_envelope(data=data, state=state)
    envelope["status"] = "partial" if state in {"partial", "stale"} else "success"
    envelope["metadata"].update(
        {
            "freshness": {
                "freshness_status": freshness_status,
                "freshness_expires_at": None,
                "last_updated_at": data["freshness_date"],
                "is_stale": freshness_status == "stale",
            },
            "confidence": {
                "level": confidence,
                "label": f"{confidence.title()} confidence",
            },
            "warnings": data["warnings"],
            "source_summary": data["source_provenance_summary"],
            "limitations": data["limitations"],
            "public_safe": True,
        }
    )
    return envelope


def _state_for_payload(payload: BaseModel) -> str:
    freshness = payload.freshness
    confidence = payload.confidence
    if freshness.freshness_status is FreshnessStatus.STALE:
        return "stale"
    if confidence.level in {Confidence.LOW, Confidence.UNKNOWN}:
        return "partial"
    return "fresh"
