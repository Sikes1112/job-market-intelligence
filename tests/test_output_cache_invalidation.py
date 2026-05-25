from datetime import UTC, datetime

from sqlalchemy.orm import Session

from backend.outputs.cache import load_cached_output
from backend.outputs.cache_repository import OutputCacheRepository
from backend.outputs.invalidation import OutputCacheInvalidationService
from backend.outputs.models import OutputMetadata
from backend.outputs.service import OutputAssemblyService
from backend.outputs.types import OutputType
from backend.refresh.adapters import LocalRefreshQueueAdapter
from backend.refresh.handlers import RefreshHandlerDispatcher
from backend.refresh.job_types import RefreshJobType
from backend.refresh.output_rebuild import make_output_rebuild_handler
from backend.refresh.runner import RefreshWorkerRunner
from backend.refresh.status import RefreshJobStatus
from tests.test_outputs_service import (
    _seed_company,
    _seed_entry_level,
    _seed_hiring,
    _seed_presence,
    _seed_region,
    _seed_score,
    _service,
)


def _seed_region_output(session: Session) -> tuple[OutputAssemblyService, OutputMetadata]:
    _seed_region(session, region_id="greater_boston")
    _seed_company(session, company_id="comp_a")
    _seed_presence(session, company_id="comp_a", region_id="greater_boston")
    _seed_hiring(session, company_id="comp_a", region_id="greater_boston")
    _seed_entry_level(session, company_id="comp_a", region_id="greater_boston")
    _seed_score(session, region_id="greater_boston")
    service = _service(session)
    result = service.build_region("greater_boston")
    return service, result.metadata


def test_output_cache_records_can_be_created_and_read(session: Session) -> None:
    _, row = _seed_region_output(session)

    cached = load_cached_output(row)

    assert row.cached_payload is not None
    assert row.source_version_bundle
    assert row.source_version_refs
    assert row.source_bundle_ref
    assert cached is not None
    assert cached.region.region_id == "greater_boston"


def test_fresh_cached_output_is_returned_without_reassembly(
    session: Session, monkeypatch
) -> None:
    service, _row = _seed_region_output(session)

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("live assembly should be fallback-only when cache is valid")

    monkeypatch.setattr(service, "_assemble_region", fail_if_called)

    result = service.read_region("greater_boston")

    assert result.action == "cached"
    assert result.payload.region.region_id == "greater_boston"


def test_marking_output_stale_preserves_source_refs_and_enqueues_rebuild(
    session: Session,
) -> None:
    _, row = _seed_region_output(session)
    original_refs = tuple(row.source_version_refs)
    original_bundle_ref = row.source_bundle_ref
    queue = LocalRefreshQueueAdapter()

    result = OutputCacheInvalidationService(
        OutputCacheRepository(session), queue
    ).mark_output_stale(
        row.output_id,
        reason="score changed",
        now=datetime(2026, 5, 24, 12, 0, tzinfo=UTC),
    )

    session.refresh(row)
    assert result.stale_output_ids == (row.output_id,)
    assert row.state == "stale"
    assert row.stale_reason == "score changed"
    assert tuple(row.source_version_refs) == original_refs
    assert row.source_bundle_ref == original_bundle_ref
    assert len(result.enqueue_results) == 1
    assert result.enqueue_results[0].request.job_type is RefreshJobType.OUTPUT_REBUILD
    assert result.enqueue_results[0].outcome == "enqueued"


def test_duplicate_active_output_rebuild_jobs_are_suppressed(session: Session) -> None:
    _, row = _seed_region_output(session)
    queue = LocalRefreshQueueAdapter()
    invalidation = OutputCacheInvalidationService(OutputCacheRepository(session), queue)

    first = invalidation.mark_output_stale(row.output_id, reason="first")
    second = invalidation.mark_output_stale(row.output_id, reason="second")

    assert first.enqueue_results[0].outcome == "enqueued"
    assert second.enqueue_results[0].outcome == "already_active"
    assert first.enqueue_results[0].request.stable_job_key == row.rebuild_job_key


def test_output_rebuild_handler_updates_cache_on_success(session: Session) -> None:
    service, row = _seed_region_output(session)
    queue = LocalRefreshQueueAdapter()
    cache_repo = OutputCacheRepository(session)
    invalidation = OutputCacheInvalidationService(cache_repo, queue)
    invalidation.mark_output_stale(row.output_id, reason="data changed")
    dispatcher = RefreshHandlerDispatcher()
    dispatcher.register(
        RefreshJobType.OUTPUT_REBUILD,
        make_output_rebuild_handler(cache_repo=cache_repo, output_service=service),
    )

    record = RefreshWorkerRunner(queue, dispatcher=dispatcher).run_next()

    session.refresh(row)
    assert record is not None
    assert record.status is RefreshJobStatus.SUCCEEDED
    assert row.state == "fresh"
    assert row.cached_payload is not None
    assert row.rebuilt_at is not None
    assert row.latest_rebuild_status == "succeeded"
    assert row.latest_rebuild_failure_reason is None


def test_output_rebuild_handler_records_failure_reason(session: Session) -> None:
    row = OutputMetadata(
        output_id="out_region_missing",
        output_type=OutputType.REGION_OUTPUT.value,
        subject_id="missing_region",
        state="stale",
        source_version_bundle={"missing": 1},
        source_version_refs=["missing=1"],
        source_bundle_ref="source_bundle:missing",
    )
    session.add(row)
    session.flush()
    queue = LocalRefreshQueueAdapter()
    invalidation = OutputCacheInvalidationService(OutputCacheRepository(session), queue)
    invalidation.mark_output_stale(row.output_id, reason="manual repair")
    service = _service(session)
    dispatcher = RefreshHandlerDispatcher()
    dispatcher.register(
        RefreshJobType.OUTPUT_REBUILD,
        make_output_rebuild_handler(
            cache_repo=OutputCacheRepository(session),
            output_service=service,
        ),
    )

    record = RefreshWorkerRunner(queue, dispatcher=dispatcher).run_next()

    session.refresh(row)
    assert record is not None
    assert record.status is RefreshJobStatus.FAILED
    assert "output_rebuild_failed" in record.failure_reason
    assert row.latest_rebuild_status == "failed"
    assert "MissingRegionForOutput" in row.latest_rebuild_failure_reason


def test_stale_output_observability_counts_by_type(session: Session) -> None:
    _, row = _seed_region_output(session)
    company = OutputMetadata(
        output_id="out_company_comp_a",
        output_type=OutputType.COMPANY_OUTPUT.value,
        subject_id="comp_a",
        state="stale",
    )
    session.add(company)
    session.flush()
    OutputCacheInvalidationService(
        OutputCacheRepository(session), LocalRefreshQueueAdapter()
    ).mark_output_stale(row.output_id, reason="region stale")

    summary = OutputCacheRepository(session).observability()

    assert summary.stale_output_count == 2
    assert summary.stale_outputs_by_type == {
        "company_output": 1,
        "region_output": 1,
    }


def test_api_read_path_serves_fresh_cache_without_redis(api_client, session) -> None:
    _seed_region_output(session)

    response = api_client.get("/regions/greater_boston")

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["region_id"] == "greater_boston"
    assert body["metadata"]["state"] == "fresh"


def test_api_read_path_surfaces_stale_cached_output(api_client, session) -> None:
    _, row = _seed_region_output(session)
    OutputCacheInvalidationService(
        OutputCacheRepository(session), LocalRefreshQueueAdapter()
    ).mark_output_stale(row.output_id, reason="scheduled invalidation")

    response = api_client.get("/regions/greater_boston")

    assert response.status_code == 200
    body = response.json()
    assert body["metadata"]["state"] == "stale"
    assert body["metadata"]["freshness"]["is_stale"] is True
    assert body["metadata"]["freshness"]["freshness_status"] == "stale"
    assert body["metadata"]["warnings"][0]["warning_code"] == "output_cache_stale"


def test_api_read_path_does_not_import_refresh_execution_runtime() -> None:
    import backend.api.routes as routes

    assert not hasattr(routes, "RefreshWorkerRunner")
    assert not hasattr(routes, "execute_refresh_job_payload")
