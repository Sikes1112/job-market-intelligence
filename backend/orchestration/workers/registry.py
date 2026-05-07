"""Worker registry: ``JobType`` → handler factory.

Each handler factory is a callable that takes a SQLAlchemy ``Session`` and
returns a per-request ``handler(request) -> JobResponse`` callable. The
runner builds a fresh handler per request so the wired-up service can
share the runtime's session.

Slice 14 registers every implemented handler. The deferred handlers
(``personal_overlay_query`` is interactive-only via the API,
``contextual_challenge_build`` is Slice 17, ``audit`` is Slice 16) are
intentionally **not** registered.
"""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.orm import Session

from backend.companies.repository import CompanyRepository
from backend.companies.service import CompanyService
from backend.entry_level.repository import EntryLevelRepository
from backend.entry_level.service import EntryLevelService
from backend.geography.repository import RegionRepository
from backend.geography.service import GeographyService
from backend.hiring.repository import HiringRepository
from backend.hiring.service import HiringService
from backend.orchestration.jobs.eligibility_classification import (
    handle_eligibility_classification,
)
from backend.orchestration.jobs.entry_level_refresh import (
    handle_entry_level_refresh,
)
from backend.orchestration.jobs.envelopes import JobRequest, JobResponse
from backend.orchestration.jobs.geography_build import handle_geography_build
from backend.orchestration.jobs.hiring_refresh import handle_hiring_refresh
from backend.orchestration.jobs.presence_mapping import handle_presence_mapping
from backend.orchestration.jobs.region_score_recompute import (
    handle_region_score_recompute,
)
from backend.orchestration.jobs.types import JobType
from backend.outputs.repository import OutputMetadataRepository
from backend.outputs.service import OutputAssemblyService
from backend.presence.repository import PresenceRepository
from backend.presence.service import PresenceService
from backend.scoring.repository import RegionScoreRepository
from backend.scoring.service import RegionScoringService

# Output handlers
from backend.orchestration.jobs.comparison_cache_build import (  # isort: skip
    handle_comparison_cache_build,
)
from backend.orchestration.jobs.company_output_build import (  # isort: skip
    handle_company_output_build,
)
from backend.orchestration.jobs.region_output_build import (  # isort: skip
    handle_region_output_build,
)


HandlerCallable = Callable[[JobRequest], JobResponse]
HandlerFactory = Callable[[Session], HandlerCallable]


# ---------------------------------------------------------------------------
# Per-handler factories
# ---------------------------------------------------------------------------


def _geography_factory(session: Session) -> HandlerCallable:
    service = GeographyService(RegionRepository(session))
    return lambda request: handle_geography_build(request, service)


def _eligibility_factory(session: Session) -> HandlerCallable:
    service = CompanyService(CompanyRepository(session))
    return lambda request: handle_eligibility_classification(request, service)


def _presence_factory(session: Session) -> HandlerCallable:
    service = PresenceService(
        PresenceRepository(session),
        company_repo=CompanyRepository(session),
        region_repo=RegionRepository(session),
    )
    return lambda request: handle_presence_mapping(request, service)


def _hiring_factory(session: Session) -> HandlerCallable:
    service = HiringService(
        HiringRepository(session),
        presence_repo=PresenceRepository(session),
    )
    return lambda request: handle_hiring_refresh(request, service)


def _entry_level_factory(session: Session) -> HandlerCallable:
    service = EntryLevelService(
        EntryLevelRepository(session),
        hiring_repo=HiringRepository(session),
    )
    return lambda request: handle_entry_level_refresh(request, service)


def _region_score_factory(session: Session) -> HandlerCallable:
    service = RegionScoringService(
        RegionScoreRepository(session),
        region_repo=RegionRepository(session),
    )
    return lambda request: handle_region_score_recompute(request, service)


def _output_assembly_service(session: Session) -> OutputAssemblyService:
    return OutputAssemblyService(
        OutputMetadataRepository(session),
        session=session,
        region_repo=RegionRepository(session),
        company_repo=CompanyRepository(session),
        presence_repo=PresenceRepository(session),
        hiring_repo=HiringRepository(session),
        entry_level_repo=EntryLevelRepository(session),
        score_repo=RegionScoreRepository(session),
    )


def _region_output_factory(session: Session) -> HandlerCallable:
    service = _output_assembly_service(session)
    return lambda request: handle_region_output_build(request, service)


def _company_output_factory(session: Session) -> HandlerCallable:
    service = _output_assembly_service(session)
    return lambda request: handle_company_output_build(request, service)


def _comparison_cache_factory(session: Session) -> HandlerCallable:
    service = _output_assembly_service(session)
    return lambda request: handle_comparison_cache_build(request, service)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class WorkerRegistry:
    """Holds the JobType → handler-factory mapping.

    The runner consults this registry per dispatch. Construction is cheap;
    the default registry registers every handler that ships in MVP. Tests
    can construct an empty registry and register stub handlers.
    """

    def __init__(self) -> None:
        self._factories: dict[JobType, HandlerFactory] = {}

    def register(self, job_type: JobType, factory: HandlerFactory) -> None:
        self._factories[job_type] = factory

    def has(self, job_type: JobType) -> bool:
        return job_type in self._factories

    def get(self, job_type: JobType) -> HandlerFactory | None:
        return self._factories.get(job_type)

    def registered_types(self) -> frozenset[JobType]:
        return frozenset(self._factories)


def default_registry() -> WorkerRegistry:
    """Return a registry populated with every implemented handler.

    Excluded:

    * ``PERSONAL_OVERLAY_QUERY`` — Slice 13 is interactive (HTTP) only.
    * ``CONTEXTUAL_CHALLENGE_BUILD`` — Slice 17 hasn't shipped yet.
    * ``AUDIT`` — Slice 16 hasn't shipped yet.
    * ``COMPANY_UNIVERSE_INTAKE`` — no handler implemented yet (real
      ingestion is Deferred A).
    """
    registry = WorkerRegistry()
    registry.register(JobType.GEOGRAPHY_BUILD, _geography_factory)
    registry.register(JobType.ELIGIBILITY_CLASSIFICATION, _eligibility_factory)
    registry.register(JobType.PRESENCE_MAPPING, _presence_factory)
    registry.register(JobType.HIRING_REFRESH, _hiring_factory)
    registry.register(JobType.ENTRY_LEVEL_REFRESH, _entry_level_factory)
    registry.register(JobType.REGION_SCORE_RECOMPUTE, _region_score_factory)
    registry.register(JobType.REGION_OUTPUT_BUILD, _region_output_factory)
    registry.register(JobType.COMPANY_OUTPUT_BUILD, _company_output_factory)
    registry.register(JobType.COMPARISON_CACHE_BUILD, _comparison_cache_factory)
    return registry
