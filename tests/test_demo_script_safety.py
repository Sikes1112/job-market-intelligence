import pytest

from backend.config.settings import Settings
from backend.shared.demo_safety import (
    ALLOW_NON_LOCAL_DEMO_DB_ENV,
    ensure_demo_database_target_allowed,
)


def test_demo_database_target_allows_local_sqlite() -> None:
    settings = Settings(app_env="local", database_url="sqlite:///demo.db", _env_file=None)

    ensure_demo_database_target_allowed(settings, "sqlite:///demo.db")


@pytest.mark.parametrize("app_env", ["public_demo", "staging", "production", "prod"])
def test_demo_database_target_blocks_production_environments(app_env: str) -> None:
    settings = Settings(
        app_env=app_env,
        database_url="postgresql://user:secret@example.test/db",
        cors_allowed_origins="https://demo.example",
        auth0_issuer=("https://tenant.example.test/" if app_env != "public_demo" else ""),
        auth0_audience="https://api.example.test" if app_env != "public_demo" else "",
        release_id="demo-safety-test" if app_env != "public_demo" else "unknown",
        _env_file=None,
    )

    with pytest.raises(SystemExit, match="blocked when APP_ENV is public_demo"):
        ensure_demo_database_target_allowed(settings, settings.database_url)


def test_demo_database_target_blocks_non_sqlite_without_confirmation() -> None:
    settings = Settings(
        app_env="local",
        database_url="postgresql://user:secret@example.test/demo",
        _env_file=None,
    )

    with pytest.raises(SystemExit, match=ALLOW_NON_LOCAL_DEMO_DB_ENV):
        ensure_demo_database_target_allowed(settings, settings.database_url)


def test_demo_database_target_allows_non_sqlite_with_explicit_confirmation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(
        app_env="local",
        database_url="postgresql://user:secret@example.test/demo",
        _env_file=None,
    )
    monkeypatch.setenv(ALLOW_NON_LOCAL_DEMO_DB_ENV, "true")

    ensure_demo_database_target_allowed(settings, settings.database_url)
