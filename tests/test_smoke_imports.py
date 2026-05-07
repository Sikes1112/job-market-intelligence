import importlib

import pytest

BACKEND_PACKAGES = [
    "backend",
    "backend.api",
    "backend.audit",
    "backend.companies",
    "backend.config",
    "backend.entry_level",
    "backend.geography",
    "backend.hiring",
    "backend.orchestration",
    "backend.orchestration.events",
    "backend.orchestration.invalidation",
    "backend.orchestration.jobs",
    "backend.orchestration.queues",
    "backend.orchestration.scheduler",
    "backend.orchestration.state_machine",
    "backend.orchestration.workers",
    "backend.outputs",
    "backend.personalization",
    "backend.presence",
    "backend.scoring",
    "backend.shared",
]


@pytest.mark.parametrize("module_name", BACKEND_PACKAGES)
def test_backend_package_imports(module_name: str) -> None:
    importlib.import_module(module_name)
