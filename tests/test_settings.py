from collections.abc import Iterator

import pytest
from pydantic import ValidationError

from backend.config.settings import AppEnv, Settings, get_settings, redact_database_url

SETTINGS_ENV_VARS = (
    "APP_ENV",
    "DATABASE_URL",
    "DATABASE_POOL_SIZE",
    "DATABASE_MAX_OVERFLOW",
    "DATABASE_POOL_RECYCLE_SECONDS",
    "CORS_ALLOWED_ORIGINS",
    "API_DOCS_ENABLED",
    "BETA_ACCESS_REQUIRED",
    "LOG_LEVEL",
    "SERVICE_NAME",
    "RELEASE_ID",
    "RENDER_GIT_COMMIT",
    "RENDER_EXTERNAL_URL",
    "PUBLIC_ORIGIN",
    "FRONTEND_DIST_DIR",
    "READINESS_REQUIRE_MIGRATION_CURRENT",
    "JOB_STALE_AFTER_SECONDS",
    "ERROR_MONITORING_DSN",
    "RATE_LIMIT_ENABLED",
    "SECURITY_HEADERS_ENABLED",
    "MAX_REQUEST_BODY_BYTES",
    "RATE_LIMIT_REQUESTS",
    "RATE_LIMIT_WINDOW_SECONDS",
    "RATE_LIMIT_ANONYMOUS_REQUESTS",
    "RATE_LIMIT_ANONYMOUS_WINDOW_SECONDS",
    "RATE_LIMIT_AUTHENTICATED_REQUESTS",
    "RATE_LIMIT_AUTHENTICATED_WINDOW_SECONDS",
    "RATE_LIMIT_EXPENSIVE_REQUESTS",
    "RATE_LIMIT_EXPENSIVE_WINDOW_SECONDS",
    "RATE_LIMIT_MUTATION_REQUESTS",
    "RATE_LIMIT_MUTATION_WINDOW_SECONDS",
    "GUEST_SESSION_TTL_SECONDS",
    "GUEST_SESSION_ISSUE_REQUESTS",
    "GUEST_SESSION_ISSUE_WINDOW_SECONDS",
    "GUEST_MAX_ACTIVE_SESSIONS",
    "GUEST_MAX_MUTATIONS_PER_SESSION",
    "GUEST_MAX_DATABASE_BYTES",
    "GUEST_MAX_CAREER_IDENTITY_FACTS",
    "GUEST_MAX_SAVED_COMPARISONS",
    "GUEST_MAX_DECISIONS",
    "GUEST_MAX_DECISION_OPTIONS",
    "GUEST_MAX_ACTIONS",
    "GUEST_MAX_APPLICATIONS",
    "GUEST_MAX_RECOMMENDATION_SNAPSHOTS",
    "STRIPE_SECRET_KEY",
    "STRIPE_WEBHOOK_SECRET",
    "STRIPE_SUCCESS_URL",
    "STRIPE_CANCEL_URL",
    "STRIPE_BILLING_PORTAL_RETURN_URL",
    "STRIPE_PRICE_INDIVIDUAL_MONTHLY",
    "STRIPE_PRICE_INDIVIDUAL_ANNUAL",
    "STRIPE_PRICE_STUDENT_ANNUAL",
    "STRIPE_PRICE_CAREER_CENTER_LICENSE",
    "STRIPE_PRICE_BOOTCAMP_LICENSE",
    "STRIPE_PRICE_UNIVERSITY_LICENSE",
    "STRIPE_PRICE_WORKFORCE_BOARD_LICENSE",
)


@pytest.fixture(autouse=True)
def clean_settings_environment(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    for name in SETTINGS_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_default_settings_are_local_and_demo_safe() -> None:
    settings = Settings(_env_file=None)

    assert settings.app_env == AppEnv.LOCAL
    assert settings.database_url == "sqlite:///./jmi.db"
    assert settings.database_pool_size == 5
    assert settings.database_max_overflow == 10
    assert settings.database_pool_recycle_seconds == 300
    assert settings.cors_allowed_origin_list == []
    assert settings.log_level == "INFO"
    assert settings.service_name == "jmi-backend"
    assert settings.release_id == "unknown"
    assert settings.api_docs_enabled is True
    assert settings.beta_access_required is False
    assert settings.readiness_require_migration_current is False
    assert settings.job_stale_after_seconds == 3600
    assert settings.error_monitoring_dsn == ""
    assert settings.rate_limit_enabled is False
    assert settings.security_headers_enabled is False
    assert settings.max_request_body_bytes == 1_048_576
    assert settings.rate_limit_requests == 120
    assert settings.rate_limit_window_seconds == 60
    assert settings.rate_limit_anonymous_requests == 120
    assert settings.rate_limit_authenticated_requests == 120
    assert settings.rate_limit_expensive_requests == 20
    assert settings.rate_limit_mutation_requests == 60
    assert settings.stripe_secret_key == ""
    assert settings.stripe_webhook_secret == ""
    assert settings.stripe_price_individual_monthly == ""


def test_stripe_settings_are_optional_and_trimmed() -> None:
    settings = Settings(
        stripe_secret_key=" sk_test_example ",
        stripe_webhook_secret=" whsec_example ",
        stripe_success_url=" https://app.example/billing/success?session_id={CHECKOUT_SESSION_ID} ",
        stripe_cancel_url=" https://app.example/markets/plans ",
        stripe_billing_portal_return_url=" https://app.example/account ",
        stripe_price_individual_monthly=" price_monthly ",
        _env_file=None,
    )

    assert settings.stripe_secret_key == "sk_test_example"
    assert settings.stripe_webhook_secret == "whsec_example"
    assert settings.stripe_success_url.startswith("https://app.example")
    assert settings.stripe_price_individual_monthly == "price_monthly"


def test_stripe_redirect_urls_must_be_safe_http_urls() -> None:
    with pytest.raises(ValidationError, match="Stripe redirect URL"):
        Settings(stripe_success_url="javascript:alert(1)", _env_file=None)


def test_explicit_test_settings_can_use_local_database_default() -> None:
    settings = Settings(app_env="test", database_url="", _env_file=None)

    assert settings.app_env == AppEnv.TEST
    assert settings.database_url == "sqlite:///./jmi.db"
    assert settings.rate_limit_enabled is False
    assert settings.security_headers_enabled is False


def test_invalid_app_env_is_rejected() -> None:
    with pytest.raises(
        ValidationError,
        match="local|test|private_demo|public_demo|staging|production|dev|prod",
    ):
        Settings(app_env="qa", _env_file=None)


@pytest.mark.parametrize(
    "app_env",
    [
        AppEnv.PRIVATE_DEMO,
        AppEnv.PUBLIC_DEMO,
        AppEnv.DEV,
        AppEnv.STAGING,
        AppEnv.PRODUCTION,
        AppEnv.PROD,
    ],
)
def test_non_local_environments_require_database_url(app_env: AppEnv) -> None:
    with pytest.raises(ValidationError, match="DATABASE_URL is required"):
        Settings(app_env=app_env, database_url="", _env_file=None)


def test_public_demo_requires_explicit_database_and_is_read_only() -> None:
    settings = Settings(
        app_env="public-demo",
        database_url="sqlite:///public-demo.db",
        cors_allowed_origins="https://demo.example",
        _env_file=None,
    )

    assert settings.app_env == AppEnv.PUBLIC_DEMO
    assert settings.is_public_demo_read_only is True
    assert settings.cors_allowed_origin_list == ["https://demo.example"]
    assert settings.rate_limit_enabled is True
    assert settings.security_headers_enabled is True
    assert settings.max_request_body_bytes == 65_536
    assert settings.rate_limit_requests == 60
    assert settings.rate_limit_window_seconds == 60
    assert settings.rate_limit_expensive_requests == 20
    assert settings.rate_limit_mutation_requests == 60
    assert settings.readiness_require_migration_current is False


def test_public_demo_requires_explicit_cors_origin() -> None:
    with pytest.raises(ValidationError, match="CORS_ALLOWED_ORIGINS"):
        Settings(
            app_env="public_demo",
            database_url="sqlite:///public-demo.db",
            _env_file=None,
        )


@pytest.mark.parametrize(
    ("setting_name", "error_message"),
    [
        ("rate_limit_enabled", "RATE_LIMIT_ENABLED must be true"),
        ("security_headers_enabled", "SECURITY_HEADERS_ENABLED must be true"),
    ],
)
def test_public_demo_requires_abuse_protection_flags_enabled(
    setting_name: str, error_message: str
) -> None:
    kwargs = {
        "app_env": "public_demo",
        "database_url": "sqlite:///public-demo.db",
        "cors_allowed_origins": "https://demo.example",
        setting_name: False,
        "_env_file": None,
    }

    with pytest.raises(ValidationError, match=error_message):
        Settings(**kwargs)


def test_private_demo_is_not_public_demo_read_only() -> None:
    settings = Settings(
        app_env="private_demo",
        database_url="sqlite:///private-demo.db",
        _env_file=None,
    )

    assert settings.app_env == AppEnv.PRIVATE_DEMO
    assert settings.is_public_demo_read_only is False


def test_non_local_database_url_is_accepted_without_exposing_repr() -> None:
    settings = Settings(
        app_env="production",
        database_url="postgresql://user:secret@example.test/db",
        cors_allowed_origins="https://app.example.test",
        auth0_issuer="https://tenant.example.test/",
        auth0_audience="https://api.example.test",
        release_id="release-test",
        _env_file=None,
    )

    assert settings.app_env == AppEnv.PRODUCTION
    assert settings.database_url == "postgresql://user:secret@example.test/db"
    assert settings.readiness_require_migration_current is True
    assert settings.api_docs_enabled is False
    assert settings.beta_access_required is True
    assert "secret" not in repr(settings)


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"cors_allowed_origins": ""}, "CORS_ALLOWED_ORIGINS"),
        ({"cors_allowed_origins": "http://app.example.test"}, "must use HTTPS"),
        ({"auth0_issuer": ""}, "AUTH0_ISSUER and AUTH0_AUDIENCE"),
        ({"auth0_audience": ""}, "AUTH0_ISSUER and AUTH0_AUDIENCE"),
        ({"release_id": "unknown"}, "RELEASE_ID is required"),
        ({"api_docs_enabled": True}, "API_DOCS_ENABLED must be false"),
    ],
)
def test_production_rejects_missing_or_unsafe_critical_config(
    override: dict[str, object], message: str
) -> None:
    values: dict[str, object] = {
        "app_env": "production",
        "database_url": "postgresql://user:secret@example.test/db",
        "cors_allowed_origins": "https://app.example.test",
        "auth0_issuer": "https://tenant.example.test/",
        "auth0_audience": "https://api.example.test",
        "release_id": "release-test",
        "_env_file": None,
    }
    values.update(override)

    with pytest.raises(ValidationError, match=message):
        Settings(**values)


def test_invalid_database_url_is_rejected_without_echoing_value() -> None:
    with pytest.raises(ValidationError, match="valid SQLAlchemy URL") as exc_info:
        Settings(app_env="prod", database_url="not a database url", _env_file=None)

    assert "not a database url" not in str(exc_info.value)


def test_cors_allowed_origins_parse_comma_separated_values() -> None:
    settings = Settings(
        cors_allowed_origins=" http://localhost:5173,https://example.test,http://localhost:5173 ",
        _env_file=None,
    )

    assert settings.cors_allowed_origins == "http://localhost:5173,https://example.test"
    assert settings.cors_allowed_origin_list == [
        "http://localhost:5173",
        "https://example.test",
    ]


def test_cors_allowed_origins_parse_json_list_values() -> None:
    settings = Settings(
        cors_allowed_origins='["http://localhost:5173", "https://example.test"]',
        _env_file=None,
    )

    assert settings.cors_allowed_origin_list == [
        "http://localhost:5173",
        "https://example.test",
    ]


def test_cors_wildcards_are_rejected() -> None:
    with pytest.raises(ValidationError, match="wildcard"):
        Settings(cors_allowed_origins="*", _env_file=None)


@pytest.mark.parametrize(
    "origin",
    [
        "localhost:5173",
        "ftp://example.test",
        "https://example.test/path",
        "https://example.test?debug=true",
        "https://user:password@example.test",
    ],
)
def test_malformed_cors_allowed_origins_are_rejected(origin: str) -> None:
    with pytest.raises(ValidationError, match="CORS_ALLOWED_ORIGINS"):
        Settings(cors_allowed_origins=origin, _env_file=None)


def test_cors_allowed_origins_normalizes_root_slash() -> None:
    settings = Settings(
        cors_allowed_origins="HTTPS://Example.Test/",
        _env_file=None,
    )

    assert settings.cors_allowed_origin_list == ["https://example.test"]


def test_log_level_is_normalized_and_validated() -> None:
    assert Settings(log_level="debug", _env_file=None).log_level == "DEBUG"

    with pytest.raises(ValidationError, match="LOG_LEVEL"):
        Settings(log_level="verbose", _env_file=None)


def test_service_name_must_not_be_whitespace() -> None:
    with pytest.raises(ValidationError, match="SERVICE_NAME"):
        Settings(service_name="   ", _env_file=None)


def test_feature_flags_parse_from_boolean_strings() -> None:
    settings = Settings(
        rate_limit_enabled="true",
        security_headers_enabled="0",
        _env_file=None,
    )

    assert settings.rate_limit_enabled is True
    assert settings.security_headers_enabled is False


def test_feature_flags_reject_unknown_boolean_strings() -> None:
    with pytest.raises(ValidationError, match="boolean"):
        Settings(rate_limit_enabled="sometimes", _env_file=None)


def test_api_protection_numeric_settings_must_be_positive() -> None:
    with pytest.raises(ValidationError, match="value must be >= 1"):
        Settings(max_request_body_bytes=0, _env_file=None)
    with pytest.raises(ValidationError, match="value must be >= 1"):
        Settings(rate_limit_requests=0, _env_file=None)
    with pytest.raises(ValidationError, match="value must be >= 1"):
        Settings(rate_limit_window_seconds=0, _env_file=None)
    with pytest.raises(ValidationError, match="value must be >= 1"):
        Settings(rate_limit_expensive_requests=0, _env_file=None)
    with pytest.raises(ValidationError, match="value must be >= 1"):
        Settings(rate_limit_mutation_window_seconds=0, _env_file=None)


def test_api_protection_numeric_settings_have_sane_upper_bounds() -> None:
    with pytest.raises(ValidationError, match="value must be <="):
        Settings(max_request_body_bytes=10 * 1024 * 1024 + 1, _env_file=None)
    with pytest.raises(ValidationError, match="value must be <="):
        Settings(rate_limit_requests=10_001, _env_file=None)
    with pytest.raises(ValidationError, match="value must be <="):
        Settings(rate_limit_window_seconds=3_601, _env_file=None)
    with pytest.raises(ValidationError, match="value must be <="):
        Settings(rate_limit_expensive_requests=10_001, _env_file=None)
    with pytest.raises(ValidationError, match="value must be <="):
        Settings(rate_limit_mutation_window_seconds=3_601, _env_file=None)


def test_blank_api_protection_numeric_settings_use_environment_defaults() -> None:
    settings = Settings(
        max_request_body_bytes="",
        rate_limit_requests="",
        rate_limit_window_seconds="",
        _env_file=None,
    )

    assert settings.max_request_body_bytes == 1_048_576
    assert settings.rate_limit_requests == 120
    assert settings.rate_limit_window_seconds == 60
    assert settings.rate_limit_expensive_requests == 20
    assert settings.rate_limit_mutation_requests == 60


def test_endpoint_class_rate_limit_settings_can_be_configured() -> None:
    settings = Settings(
        rate_limit_requests=200,
        rate_limit_anonymous_requests=50,
        rate_limit_authenticated_requests=150,
        rate_limit_expensive_requests=8,
        rate_limit_mutation_requests=40,
        rate_limit_anonymous_window_seconds=30,
        rate_limit_authenticated_window_seconds=45,
        rate_limit_expensive_window_seconds=90,
        rate_limit_mutation_window_seconds=120,
        _env_file=None,
    )

    assert settings.rate_limit_anonymous_requests == 50
    assert settings.rate_limit_authenticated_requests == 150
    assert settings.rate_limit_expensive_requests == 8
    assert settings.rate_limit_mutation_requests == 40
    assert settings.rate_limit_anonymous_window_seconds == 30
    assert settings.rate_limit_authenticated_window_seconds == 45
    assert settings.rate_limit_expensive_window_seconds == 90
    assert settings.rate_limit_mutation_window_seconds == 120


@pytest.mark.parametrize("app_env", [AppEnv.DEV, AppEnv.PRIVATE_DEMO])
def test_non_strict_non_local_defaults_deferred_flags_to_disabled(app_env: AppEnv) -> None:
    settings = Settings(
        app_env=app_env,
        database_url="sqlite:///dev.db",
        _env_file=None,
    )

    assert settings.rate_limit_enabled is False
    assert settings.security_headers_enabled is False


def test_staging_production_and_legacy_prod_default_deferred_flags_to_enabled() -> None:
    staging = Settings(
        app_env="staging",
        database_url="postgresql://user:secret@example.test/staging",
        cors_allowed_origins="https://staging.example.test",
        auth0_issuer="https://tenant.example.test/",
        auth0_audience="https://api.example.test",
        release_id="staging-test",
        _env_file=None,
    )
    production = Settings(
        app_env="production",
        database_url="postgresql://user:secret@example.test/prod",
        cors_allowed_origins="https://app.example.test",
        auth0_issuer="https://tenant.example.test/",
        auth0_audience="https://api.example.test",
        release_id="production-test",
        _env_file=None,
    )
    legacy_prod = Settings(
        app_env="prod",
        database_url="postgresql://user:secret@example.test/prod",
        cors_allowed_origins="https://app.example.test",
        auth0_issuer="https://tenant.example.test/",
        auth0_audience="https://api.example.test",
        release_id="prod-test",
        _env_file=None,
    )

    assert staging.rate_limit_enabled is True
    assert staging.security_headers_enabled is True
    assert production.rate_limit_enabled is True
    assert production.security_headers_enabled is True
    assert legacy_prod.rate_limit_enabled is True
    assert legacy_prod.security_headers_enabled is True


@pytest.mark.parametrize("app_env", [AppEnv.STAGING, AppEnv.PRODUCTION, AppEnv.PROD])
def test_staging_and_prod_reject_sqlite_database_url(app_env: AppEnv) -> None:
    with pytest.raises(ValidationError, match="must not use SQLite"):
        Settings(app_env=app_env, database_url="sqlite:///prod.db", _env_file=None)


@pytest.mark.parametrize(
    ("setting_name", "error_message"),
    [
        ("rate_limit_enabled", "RATE_LIMIT_ENABLED must be true"),
        ("security_headers_enabled", "SECURITY_HEADERS_ENABLED must be true"),
    ],
)
def test_staging_and_prod_require_protection_flags_enabled(
    setting_name: str, error_message: str
) -> None:
    kwargs = {
        "app_env": "prod",
        "database_url": "postgresql://user:secret@example.test/prod",
        setting_name: False,
        "_env_file": None,
    }

    with pytest.raises(ValidationError, match=error_message):
        Settings(**kwargs)


def test_get_settings_reads_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///env-test.db")
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "yes")
    monkeypatch.setenv("SECURITY_HEADERS_ENABLED", "no")

    settings = get_settings()

    assert settings.app_env == AppEnv.TEST
    assert settings.database_url == "sqlite:///env-test.db"
    assert settings.rate_limit_enabled is True
    assert settings.security_headers_enabled is False


def test_redact_database_url_hides_credentials() -> None:
    redacted = redact_database_url("postgresql://user:secret@example.test/db?sslmode=require")

    assert "secret" not in redacted
    assert "user:***@" in redacted
    assert redact_database_url("not a url") == "<invalid database url>"
