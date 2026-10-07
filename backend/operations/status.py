from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.config.settings import Settings
from backend.current_opportunities.models import OpportunityAcquisitionRun, OpportunityDataSource
from backend.current_opportunities.schemas import AcquisitionRunStatus
from backend.operations.metrics import metrics_registry_from_app_state
from backend.operations.migrations import (
    MigrationStatus,
    database_migration_status,
    database_migration_status_from_connection,
)
from backend.orchestration.jobs.models import Job
from backend.shared.redaction import redact_sensitive


def liveness_payload(settings: Settings) -> dict[str, Any]:
    return {
        "status": "ok",
        "service": settings.service_name,
        "environment": settings.app_env.value,
        "release_id": settings.release_id,
    }


def readiness_payload(engine: object, settings: Settings) -> tuple[int, dict[str, Any]]:
    checks = {"config": "ok", "database": "ok"}
    status_code = 200
    status_value = "ready"

    try:
        with engine.connect() as connection:  # type: ignore[attr-defined]
            connection.execute(text("SELECT 1")).scalar_one()
    except Exception:
        checks["database"] = "failed"
        status_code = 503
        status_value = "not_ready"

    schema_status: MigrationStatus | None = None
    if checks["database"] == "ok":
        schema_status = database_migration_status(engine, settings.database_url)  # type: ignore[arg-type]
        checks["schema"] = schema_status.status
        if settings.readiness_require_migration_current and schema_status.status != "current":
            status_code = 503
            status_value = "not_ready"

    return status_code, {
        "status": status_value,
        "service": settings.service_name,
        "environment": settings.app_env.value,
        "release_id": settings.release_id,
        "checks": checks,
        **({"schema": schema_status.as_dict()} if schema_status is not None else {}),
    }


def readiness_payload_from_session(
    session: Session,
    settings: Settings,
) -> tuple[int, dict[str, Any]]:
    checks = {"config": "ok", "database": "ok"}
    status_code = 200
    status_value = "ready"

    schema_status: MigrationStatus | None = None
    try:
        connection = session.connection()
        connection.execute(text("SELECT 1")).scalar_one()
        schema_status = database_migration_status_from_connection(connection, settings.database_url)
        checks["schema"] = schema_status.status
        if settings.readiness_require_migration_current and schema_status.status != "current":
            status_code = 503
            status_value = "not_ready"
    except Exception:
        checks["database"] = "failed"
        status_code = 503
        status_value = "not_ready"

    return status_code, {
        "status": status_value,
        "service": settings.service_name,
        "environment": settings.app_env.value,
        "release_id": settings.release_id,
        "checks": checks,
        **({"schema": schema_status.as_dict()} if schema_status is not None else {}),
    }


def detailed_health_payload(
    *,
    app_state: object,
    session: Session,
    settings: Settings,
) -> dict[str, Any]:
    status_code, ready = readiness_payload_from_session(session, settings)
    payload: dict[str, Any] = {
        "status": "ok" if status_code == 200 else "degraded",
        "service": settings.service_name,
        "environment": settings.app_env.value,
        "release_id": settings.release_id,
        "readiness": ready,
        "metrics": _metrics_summary(app_state),
        "jobs": job_status_summary(
            session,
            stale_after_seconds=int(settings.job_stale_after_seconds or 3600),
        ),
        "current_opportunities": opportunity_refresh_summary(
            session,
            stale_after_seconds=int(settings.job_stale_after_seconds or 3600),
        ),
        "dependencies": {
            "database": ready["checks"].get("database", "unknown"),
            "schema": ready["checks"].get("schema", "not_checked"),
            "error_monitoring": "configured" if settings.error_monitoring_dsn else "not_configured",
        },
    }
    return redact_sensitive(payload)


def job_status_summary(session: Session, *, stale_after_seconds: int) -> dict[str, Any]:
    threshold = datetime.now(UTC) - timedelta(seconds=stale_after_seconds)
    try:
        by_status = {
            status: count
            for status, count in session.execute(
                select(Job.status, func.count()).group_by(Job.status)
            ).all()
        }
        stale_running = session.execute(
            select(func.count())
            .select_from(Job)
            .where(Job.status == "running", Job.started_at < threshold)
        ).scalar_one()
        recent_failed = session.execute(
            select(Job)
            .where(Job.status == "failed")
            .order_by(Job.updated_at.desc(), Job.job_id)
            .limit(10)
        ).scalars()
        return {
            "status": "ok",
            "by_status": by_status,
            "stale_running_count": int(stale_running),
            "recent_failures": [_safe_job_failure(row) for row in recent_failed],
        }
    except SQLAlchemyError:
        return {"status": "unavailable", "by_status": {}, "stale_running_count": 0}


def opportunity_refresh_summary(
    session: Session,
    *,
    stale_after_seconds: int,
) -> dict[str, Any]:
    threshold = datetime.now(UTC) - timedelta(seconds=stale_after_seconds)
    try:
        source_count = session.execute(
            select(func.count()).select_from(OpportunityDataSource)
        ).scalar_one()
        enabled_count = session.execute(
            select(func.count())
            .select_from(OpportunityDataSource)
            .where(OpportunityDataSource.enabled.is_(True))
        ).scalar_one()
        by_status = {
            status: count
            for status, count in session.execute(
                select(OpportunityAcquisitionRun.status, func.count()).group_by(
                    OpportunityAcquisitionRun.status
                )
            ).all()
        }
        last_success = session.execute(
            select(OpportunityAcquisitionRun)
            .where(OpportunityAcquisitionRun.status == AcquisitionRunStatus.COMPLETED.value)
            .order_by(OpportunityAcquisitionRun.completed_at.desc().nullslast())
            .limit(1)
        ).scalar_one_or_none()
        stale_running = session.execute(
            select(func.count())
            .select_from(OpportunityAcquisitionRun)
            .where(
                OpportunityAcquisitionRun.status.in_(
                    [
                        AcquisitionRunStatus.PENDING.value,
                        AcquisitionRunStatus.RUNNING.value,
                    ]
                ),
                OpportunityAcquisitionRun.started_at < threshold,
            )
        ).scalar_one()
        recent_runs = session.execute(
            select(OpportunityAcquisitionRun)
            .order_by(OpportunityAcquisitionRun.started_at.desc(), OpportunityAcquisitionRun.run_id)
            .limit(10)
        ).scalars()
        return {
            "status": "ok",
            "source_count": int(source_count),
            "enabled_source_count": int(enabled_count),
            "runs_by_status": by_status,
            "last_successful_refresh": _safe_run_summary(last_success),
            "stale_running_count": int(stale_running),
            "recent_runs": [_safe_run_summary(row) for row in recent_runs],
        }
    except SQLAlchemyError:
        return {"status": "unavailable"}


def _metrics_summary(app_state: object) -> dict[str, Any]:
    registry = metrics_registry_from_app_state(app_state)
    if registry is None:
        return {"status": "unavailable"}
    snapshot = registry.snapshot()
    return {
        "status": "ok",
        "http_series_count": len(snapshot["http"]),
    }


def _safe_job_failure(row: Job) -> dict[str, Any]:
    return {
        "job_id": row.job_id,
        "job_type": row.job_type,
        "queue_name": row.queue_name,
        "status": row.status,
        "retry_count": row.retry_count,
        "max_retries": row.max_retries,
        "error_code": row.error_code,
        "updated_at": row.updated_at,
    }


def _safe_run_summary(row: OpportunityAcquisitionRun | None) -> dict[str, Any] | None:
    if row is None:
        return None
    failure_details = row.failure_details or {}
    return {
        "run_id": row.run_id,
        "source_id": row.source_id,
        "status": row.status,
        "trigger_type": row.trigger_type,
        "started_at": row.started_at,
        "completed_at": row.completed_at,
        "retry_classification": row.retry_classification,
        "retry_count": row.retry_count,
        "counts": {
            "acquired": row.acquired_count,
            "normalized": row.normalized_count,
            "promoted": row.promoted_count,
            "duplicate": row.duplicate_count,
            "rejected": row.rejected_count,
            "warning": row.warning_count,
            "failure": row.failure_count,
        },
        "failure_summary": {
            "keys": sorted(str(key) for key in failure_details.keys())[:20],
        },
    }
