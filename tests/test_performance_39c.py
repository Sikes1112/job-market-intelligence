from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, event, text
from sqlalchemy.orm import Session

from backend.current_opportunities.models import (
    CurrentOpportunity,
    CurrentOpportunitySourceLink,
    OpportunityAcquisitionRun,
    OpportunitySourceObservation,
)
from backend.current_opportunities.service import OPPORTUNITY_LIST_MIN_SCAN_WINDOW
from tests.test_current_opportunities import (
    NOW,
    _coverage,
    _seed_market,
    _service,
    _source,
)


@contextmanager
def _count_selects(engine: Engine) -> Iterator[dict[str, int]]:
    counts = {"selects": 0}

    def before_cursor_execute(
        _conn, _cursor, statement, _parameters, _context, _executemany
    ) -> None:
        if statement.lstrip().upper().startswith("SELECT"):
            counts["selects"] += 1

    event.listen(engine, "before_cursor_execute", before_cursor_execute)
    try:
        yield counts
    finally:
        event.remove(engine, "before_cursor_execute", before_cursor_execute)


@contextmanager
def _count_loaded_current_opportunities() -> Iterator[dict[str, int]]:
    counts = {"loaded": 0}

    def loaded(_target, _context) -> None:
        counts["loaded"] += 1

    event.listen(CurrentOpportunity, "load", loaded)
    try:
        yield counts
    finally:
        event.remove(CurrentOpportunity, "load", loaded)


def test_current_opportunity_list_prefetches_links_sources_and_coverage(
    session: Session,
) -> None:
    _seed_market(session)
    service = _service(session)
    service.upsert_source(_source())
    service.upsert_coverage(_coverage())
    _seed_canonical_opportunities(session, count=12)
    session.flush()

    with _count_selects(session.bind) as counts:
        rows = service.list_opportunities(limit=5, now=NOW)

    assert len(rows) == 5
    assert counts["selects"] <= 5


def test_current_opportunity_list_materializes_bounded_candidates_for_small_page(
    session: Session,
) -> None:
    _seed_market(session)
    service = _service(session)
    service.upsert_source(_source())
    service.upsert_coverage(_coverage())
    _seed_canonical_opportunities(session, count=2000)
    session.flush()
    session.expunge_all()

    with (
        _count_selects(session.bind) as select_counts,
        _count_loaded_current_opportunities() as loaded_counts,
    ):
        rows = service.list_opportunities(limit=20, now=NOW)

    assert len(rows) == 20
    assert loaded_counts["loaded"] == OPPORTUNITY_LIST_MIN_SCAN_WINDOW
    assert select_counts["selects"] <= 5


def test_current_opportunity_list_keeps_deterministic_pagination_with_bounded_scan(
    session: Session,
) -> None:
    _seed_market(session)
    service = _service(session)
    service.upsert_source(_source())
    service.upsert_coverage(_coverage())
    _seed_canonical_opportunities(session, count=240)
    session.flush()
    session.expunge_all()

    first_page = service.list_opportunities(limit=20, offset=0, now=NOW)
    second_page = service.list_opportunities(limit=20, offset=20, now=NOW)
    empty_page = service.list_opportunities(market="missing-market", limit=20, now=NOW)

    first_ids = [row.opportunity_id for row in first_page]
    second_ids = [row.opportunity_id for row in second_page]
    assert len(first_ids) == 20
    assert len(second_ids) == 20
    assert not set(first_ids) & set(second_ids)
    assert first_ids == sorted(first_ids)
    assert second_ids == sorted(second_ids)
    assert empty_page == ()


def test_current_opportunity_query_uses_existing_filter_index(session: Session) -> None:
    _seed_market(session)
    service = _service(session)
    service.upsert_source(_source())
    service.upsert_coverage(_coverage())
    _seed_canonical_opportunities(session, count=1)
    session.flush()

    plan_rows = session.execute(
        text(
            """
            EXPLAIN QUERY PLAN
            SELECT current_opportunity_id
            FROM current_opportunities
            WHERE market_id = :market_id
              AND canonical_status = :status
              AND ranking_eligible = 1
            ORDER BY ranking_eligible DESC, last_observed_at DESC, current_opportunity_id
            LIMIT 20
            """
        ),
        {"market_id": "greater_boston", "status": "active"},
    ).all()

    plan_text = " ".join(str(row[-1]).upper() for row in plan_rows)
    assert "INDEX" in plan_text


def _seed_canonical_opportunities(session: Session, *, count: int) -> None:
    run = OpportunityAcquisitionRun(
        run_id="run_perf_direct_seed",
        source_id="src_employer",
        idempotency_key="src_employer:run_perf_direct_seed",
        status="completed",
        trigger_type="manual",
        started_at=NOW,
        completed_at=NOW,
        retry_classification="none",
        acquired_count=count,
        normalized_count=count,
        promoted_count=count,
        duplicate_count=0,
        rejected_count=0,
        warning_count=0,
        failure_count=0,
        failure_details={},
        warnings=[],
    )
    session.add(run)
    for index in range(count):
        opportunity_id = f"current_opp_perf_{index}"
        provider_record_id = f"perf-provider-{index}"
        observation_id = f"opp_obs_perf_{index}"
        session.add(
            OpportunitySourceObservation(
                source_observation_id=observation_id,
                source_id="src_employer",
                run_id=run.run_id,
                provider_record_id=provider_record_id,
                provider_record_key=f"src_employer|{provider_record_id}",
                raw_payload={"provider_record_id": provider_record_id},
                payload_hash=f"hash-{index}",
                source_values={},
                normalized_payload={},
                record_status="active",
                normalization_status="valid",
                validation_errors=[],
                observed_at=NOW,
                collected_at=NOW,
            )
        )
        session.add(
            CurrentOpportunity(
                current_opportunity_id=opportunity_id,
                canonical_identity_key=f"perf-identity-{index}",
                duplicate_group_key=f"perf-group-{index}",
                company_id="comp_acme",
                company_name="Acme Robotics",
                original_title=f"Software Engineer {index}",
                normalized_title=f"Software Engineer {index}",
                role_family="software_engineering",
                seniority_level="entry_level",
                market_id="greater_boston",
                market_label="Greater Boston",
                location_text="Greater Boston hybrid",
                work_arrangement="hybrid",
                compensation_min=100000,
                compensation_max=120000,
                compensation_currency="USD",
                compensation_interval="annual",
                employment_type="full_time",
                opportunity_type="job",
                posting_date=None,
                closing_date=None,
                application_url=f"https://jobs.acme.example/apply/{provider_record_id}",
                application_host="jobs.acme.example",
                source_url=f"https://jobs.acme.example/jobs/{provider_record_id}",
                description_text="Build cloud systems with Python.",
                skills=["Python", "Cloud"],
                requirements=["Entry-level software experience"],
                source_values={},
                normalization_confidence="high",
                identity_confidence="high",
                canonical_status="active",
                first_observed_at=NOW,
                last_observed_at=NOW,
                last_collected_at=NOW,
                canonical_updated_at=NOW,
                freshness_state="fresh",
                ranking_eligible=True,
                ranking_ineligible_reasons=[],
                warnings=[],
                source_count=1,
            )
        )
    session.flush()
    for index in range(count):
        opportunity_id = f"current_opp_perf_{index}"
        provider_record_id = f"perf-provider-{index}"
        observation_id = f"opp_obs_perf_{index}"
        session.add(
            CurrentOpportunitySourceLink(
                current_opportunity_source_link_id=f"opp_link_perf_{index}",
                current_opportunity_id=opportunity_id,
                source_id="src_employer",
                provider_record_id=provider_record_id,
                latest_observation_id=observation_id,
                source_identity_key=f"src_employer|{provider_record_id}",
                first_observed_at=NOW,
                last_observed_at=NOW,
                last_collected_at=NOW,
                active=True,
                payload_hash=f"hash-{index}",
                application_url=f"https://jobs.acme.example/apply/{provider_record_id}",
                identity_confidence="high",
            )
        )
