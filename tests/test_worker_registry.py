from backend.orchestration.jobs.types import JobType
from backend.orchestration.workers.registry import WorkerRegistry, default_registry


def test_default_registry_registers_documented_handlers() -> None:
    registry = default_registry()
    expected = frozenset(
        {
            JobType.GEOGRAPHY_BUILD,
            JobType.ELIGIBILITY_CLASSIFICATION,
            JobType.PRESENCE_MAPPING,
            JobType.HIRING_REFRESH,
            JobType.ENTRY_LEVEL_REFRESH,
            JobType.REGION_SCORE_RECOMPUTE,
            JobType.REGION_OUTPUT_BUILD,
            JobType.COMPANY_OUTPUT_BUILD,
            JobType.COMPARISON_CACHE_BUILD,
        }
    )
    assert registry.registered_types() == expected


def test_default_registry_does_not_register_deferred_handlers() -> None:
    registry = default_registry()
    # Deferred to later slices (or out of MVP runtime scope).
    assert not registry.has(JobType.PERSONAL_OVERLAY_QUERY)
    assert not registry.has(JobType.CONTEXTUAL_CHALLENGE_BUILD)
    assert not registry.has(JobType.AUDIT)
    assert not registry.has(JobType.COMPANY_UNIVERSE_INTAKE)


def test_empty_registry_get_returns_none() -> None:
    registry = WorkerRegistry()
    assert registry.get(JobType.GEOGRAPHY_BUILD) is None
    assert registry.has(JobType.GEOGRAPHY_BUILD) is False


def test_register_and_lookup() -> None:
    registry = WorkerRegistry()

    def fake_factory(session):
        def handler(request):
            raise NotImplementedError

        return handler

    registry.register(JobType.GEOGRAPHY_BUILD, fake_factory)
    assert registry.has(JobType.GEOGRAPHY_BUILD) is True
    assert registry.get(JobType.GEOGRAPHY_BUILD) is fake_factory
