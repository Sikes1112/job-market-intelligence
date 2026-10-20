import json
from enum import StrEnum
from functools import lru_cache
from typing import Any, Self
from urllib.parse import urlsplit, urlunsplit

from pydantic import Field, ValidationInfo, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


class AppEnv(StrEnum):
    # Local developer mode. May use the local SQLite default and leaves
    # public-demo read-only enforcement disabled.
    LOCAL = "local"
    # Test-only mode used by the pytest suite.
    TEST = "test"
    # Private demo mode is for restricted demos where authenticated mutation
    # workflows may still be exercised against an explicitly configured DB.
    PRIVATE_DEMO = "private_demo"
    # Public demo mode is externally viewable and fail-closed read-only for
    # durable API mutation surfaces. It is stricter than private_demo/staging
    # for writes, but it is not production.
    PUBLIC_DEMO = "public_demo"
    # Public guest demo mode serves the React application and a deliberately
    # bounded writable guest sandbox from one origin. It is separate from the
    # existing read-only public_demo mode and never enables local auth.
    PUBLIC_GUEST_DEMO = "public_guest_demo"
    # Staging mirrors production infrastructure posture without being public
    # production.
    STAGING = "staging"
    # Production is the external-production mode.
    PRODUCTION = "production"
    # Backward-compatible legacy environment strings.
    DEV = "dev"
    PROD = "prod"


LOCAL_DATABASE_URL = "sqlite:///./jmi.db"
LOG_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})
NON_LOCAL_ENVS = frozenset(
    {
        AppEnv.PRIVATE_DEMO,
        AppEnv.PUBLIC_DEMO,
        AppEnv.PUBLIC_GUEST_DEMO,
        AppEnv.STAGING,
        AppEnv.PRODUCTION,
        AppEnv.DEV,
        AppEnv.PROD,
    }
)
STRICT_DEFAULT_ENABLED_ENVS = frozenset({AppEnv.STAGING, AppEnv.PRODUCTION, AppEnv.PROD})
PUBLIC_DEMO_READ_ONLY_ENVS = frozenset({AppEnv.PUBLIC_DEMO})
PUBLIC_GUEST_ENVS = frozenset({AppEnv.PUBLIC_GUEST_DEMO})
RATE_LIMIT_DEFAULT_ENABLED_ENVS = (
    STRICT_DEFAULT_ENABLED_ENVS | PUBLIC_DEMO_READ_ONLY_ENVS | PUBLIC_GUEST_ENVS
)
SECURITY_HEADERS_DEFAULT_ENABLED_ENVS = (
    STRICT_DEFAULT_ENABLED_ENVS | PUBLIC_DEMO_READ_ONLY_ENVS | PUBLIC_GUEST_ENVS
)
DEFAULT_MAX_REQUEST_BODY_BYTES = 1_048_576
PUBLIC_DEMO_MAX_REQUEST_BODY_BYTES = 65_536
PUBLIC_GUEST_MAX_REQUEST_BODY_BYTES = 65_536
DEFAULT_RATE_LIMIT_REQUESTS = 120
PUBLIC_DEMO_RATE_LIMIT_REQUESTS = 60
DEFAULT_RATE_LIMIT_WINDOW_SECONDS = 60
DEFAULT_EXPENSIVE_RATE_LIMIT_REQUESTS = 20
DEFAULT_MUTATION_RATE_LIMIT_REQUESTS = 60
MAX_REQUEST_BODY_BYTES_LIMIT = 10 * 1024 * 1024
RATE_LIMIT_REQUESTS_LIMIT = 10_000
RATE_LIMIT_WINDOW_SECONDS_LIMIT = 3_600
DEFAULT_JOB_STALE_AFTER_SECONDS = 3_600
JOB_STALE_AFTER_SECONDS_LIMIT = 86_400


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
    )

    app_env: AppEnv = Field(default=AppEnv.LOCAL)
    log_level: str = Field(default="INFO")
    service_name: str = Field(default="jmi-backend")
    release_id: str = Field(default="unknown")
    render_git_commit: str = Field(default="")
    database_url: str = Field(default="", repr=False)
    database_pool_size: int = Field(default=5)
    database_max_overflow: int = Field(default=10)
    database_pool_recycle_seconds: int = Field(default=300)
    cors_allowed_origins: str = Field(default="")
    public_origin: str = Field(default="")
    render_external_url: str = Field(default="")
    frontend_dist_dir: str = Field(default="frontend/dist")
    api_docs_enabled: bool | None = Field(default=None)
    beta_access_required: bool | None = Field(default=None)
    readiness_require_migration_current: bool | None = Field(default=None)
    job_stale_after_seconds: int | None = Field(default=None)
    error_monitoring_dsn: str = Field(default="", repr=False)
    rate_limit_enabled: bool | None = Field(default=None)
    security_headers_enabled: bool | None = Field(default=None)
    max_request_body_bytes: int | None = Field(default=None)
    rate_limit_requests: int | None = Field(default=None)
    rate_limit_window_seconds: int | None = Field(default=None)
    rate_limit_anonymous_requests: int | None = Field(default=None)
    rate_limit_anonymous_window_seconds: int | None = Field(default=None)
    rate_limit_authenticated_requests: int | None = Field(default=None)
    rate_limit_authenticated_window_seconds: int | None = Field(default=None)
    rate_limit_expensive_requests: int | None = Field(default=None)
    rate_limit_expensive_window_seconds: int | None = Field(default=None)
    rate_limit_mutation_requests: int | None = Field(default=None)
    rate_limit_mutation_window_seconds: int | None = Field(default=None)
    auth0_issuer: str = Field(default="")
    auth0_audience: str = Field(default="")
    auth0_jwks_url: str = Field(default="")
    auth0_jwks_cache_seconds: int = Field(default=300)
    stripe_secret_key: str = Field(default="", repr=False)
    stripe_webhook_secret: str = Field(default="", repr=False)
    stripe_success_url: str = Field(default="")
    stripe_cancel_url: str = Field(default="")
    stripe_billing_portal_return_url: str = Field(default="")
    stripe_price_individual_monthly: str = Field(default="")
    stripe_price_individual_annual: str = Field(default="")
    stripe_price_student_annual: str = Field(default="")
    stripe_price_career_center_license: str = Field(default="")
    stripe_price_bootcamp_license: str = Field(default="")
    stripe_price_university_license: str = Field(default="")
    stripe_price_workforce_board_license: str = Field(default="")
    guest_session_ttl_seconds: int = Field(default=28_800)
    guest_session_issue_requests: int = Field(default=10)
    guest_session_issue_window_seconds: int = Field(default=60)
    guest_max_active_sessions: int = Field(default=250)
    guest_max_mutations_per_session: int = Field(default=500)
    guest_max_database_bytes: int = Field(default=64 * 1024 * 1024)
    guest_max_career_identity_facts: int = Field(default=50)
    guest_max_saved_comparisons: int = Field(default=25)
    guest_max_decisions: int = Field(default=25)
    guest_max_decision_options: int = Field(default=100)
    guest_max_actions: int = Field(default=100)
    guest_max_applications: int = Field(default=50)
    guest_max_recommendation_snapshots: int = Field(default=50)

    @field_validator("app_env", mode="before")
    @classmethod
    def _normalize_app_env(cls, value: AppEnv | str) -> AppEnv | str:
        if isinstance(value, str):
            return value.strip().lower().replace("-", "_")
        return value

    @field_validator("database_url", mode="before")
    @classmethod
    def _normalize_database_url_value(cls, value: str | None) -> str:
        if value is None:
            return ""
        normalized = value.strip()
        if normalized:
            try:
                make_url(normalized)
            except Exception as exc:
                raise ValueError("DATABASE_URL must be a valid SQLAlchemy URL") from exc
        return normalized

    @field_validator("log_level", mode="before")
    @classmethod
    def _normalize_log_level(cls, value: Any) -> str:
        if not isinstance(value, str):
            raise ValueError("LOG_LEVEL must be a string")
        normalized = value.strip().upper()
        if normalized not in LOG_LEVELS:
            allowed = ", ".join(sorted(LOG_LEVELS))
            raise ValueError(f"LOG_LEVEL must be one of: {allowed}")
        return normalized

    @field_validator("service_name", mode="before")
    @classmethod
    def _validate_service_name(cls, value: Any) -> str:
        if not isinstance(value, str):
            raise ValueError("SERVICE_NAME must be a string")
        normalized = value.strip()
        if not normalized:
            raise ValueError("SERVICE_NAME must not be empty")
        return normalized

    @field_validator("auth0_issuer", "auth0_audience", "auth0_jwks_url", mode="before")
    @classmethod
    def _normalize_optional_auth0_string(cls, value: Any) -> str:
        if value is None:
            return ""
        if not isinstance(value, str):
            raise ValueError("Auth0 settings must be strings")
        return value.strip()

    @field_validator(
        "stripe_secret_key",
        "stripe_webhook_secret",
        "stripe_price_individual_monthly",
        "stripe_price_individual_annual",
        "stripe_price_student_annual",
        "stripe_price_career_center_license",
        "stripe_price_bootcamp_license",
        "stripe_price_university_license",
        "stripe_price_workforce_board_license",
        mode="before",
    )
    @classmethod
    def _normalize_optional_stripe_string(cls, value: Any) -> str:
        if value is None:
            return ""
        if not isinstance(value, str):
            raise ValueError("Stripe settings must be strings")
        return value.strip()

    @field_validator(
        "stripe_success_url",
        "stripe_cancel_url",
        "stripe_billing_portal_return_url",
        mode="before",
    )
    @classmethod
    def _normalize_optional_stripe_url(cls, value: Any) -> str:
        if value is None:
            return ""
        if not isinstance(value, str):
            raise ValueError("Stripe URL settings must be strings")
        normalized = value.strip()
        if not normalized:
            return ""
        _validate_external_redirect_url(normalized)
        return normalized

    @field_validator("cors_allowed_origins", mode="before")
    @classmethod
    def _normalize_cors_allowed_origins(cls, value: Any) -> str:
        origins = _parse_cors_allowed_origins(value)
        if any("*" in origin for origin in origins):
            raise ValueError(
                "CORS_ALLOWED_ORIGINS must list exact origins; wildcard '*' is not allowed"
            )
        return ",".join(origins)

    @field_validator("public_origin", "render_external_url", mode="before")
    @classmethod
    def _normalize_public_origin(cls, value: Any) -> str:
        if value is None:
            return ""
        if not isinstance(value, str):
            raise ValueError("public origin settings must be strings")
        normalized = value.strip()
        return _normalize_cors_origin(normalized) if normalized else ""

    @field_validator("frontend_dist_dir", mode="before")
    @classmethod
    def _normalize_frontend_dist_dir(cls, value: Any) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("FRONTEND_DIST_DIR must not be empty")
        return value.strip()

    @field_validator(
        "rate_limit_enabled",
        "security_headers_enabled",
        "readiness_require_migration_current",
        "api_docs_enabled",
        "beta_access_required",
        mode="before",
    )
    @classmethod
    def _parse_optional_bool(cls, value: Any) -> bool | None:
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if not normalized:
                return None
            if normalized in {"1", "true", "t", "yes", "y", "on"}:
                return True
            if normalized in {"0", "false", "f", "no", "n", "off"}:
                return False
        raise ValueError("value must be a boolean")

    @field_validator(
        "max_request_body_bytes",
        "rate_limit_requests",
        "rate_limit_window_seconds",
        "rate_limit_anonymous_requests",
        "rate_limit_anonymous_window_seconds",
        "rate_limit_authenticated_requests",
        "rate_limit_authenticated_window_seconds",
        "rate_limit_expensive_requests",
        "rate_limit_expensive_window_seconds",
        "rate_limit_mutation_requests",
        "rate_limit_mutation_window_seconds",
        "job_stale_after_seconds",
        "guest_session_ttl_seconds",
        "guest_session_issue_requests",
        "guest_session_issue_window_seconds",
        "guest_max_active_sessions",
        "guest_max_mutations_per_session",
        "guest_max_database_bytes",
        "guest_max_career_identity_facts",
        "guest_max_saved_comparisons",
        "guest_max_decisions",
        "guest_max_decision_options",
        "guest_max_actions",
        "guest_max_applications",
        "guest_max_recommendation_snapshots",
        "database_pool_size",
        "database_pool_recycle_seconds",
        mode="before",
    )
    @classmethod
    def _validate_positive_int(cls, value: int | None, info: ValidationInfo) -> int | None:
        if value is None:
            return None
        if isinstance(value, str) and not value.strip():
            return None
        try:
            normalized = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("value must be an integer") from exc
        if normalized < 1:
            raise ValueError("value must be >= 1")
        limits = {
            "max_request_body_bytes": MAX_REQUEST_BODY_BYTES_LIMIT,
            "rate_limit_requests": RATE_LIMIT_REQUESTS_LIMIT,
            "rate_limit_anonymous_requests": RATE_LIMIT_REQUESTS_LIMIT,
            "rate_limit_authenticated_requests": RATE_LIMIT_REQUESTS_LIMIT,
            "rate_limit_expensive_requests": RATE_LIMIT_REQUESTS_LIMIT,
            "rate_limit_mutation_requests": RATE_LIMIT_REQUESTS_LIMIT,
            "rate_limit_window_seconds": RATE_LIMIT_WINDOW_SECONDS_LIMIT,
            "rate_limit_anonymous_window_seconds": RATE_LIMIT_WINDOW_SECONDS_LIMIT,
            "rate_limit_authenticated_window_seconds": RATE_LIMIT_WINDOW_SECONDS_LIMIT,
            "rate_limit_expensive_window_seconds": RATE_LIMIT_WINDOW_SECONDS_LIMIT,
            "rate_limit_mutation_window_seconds": RATE_LIMIT_WINDOW_SECONDS_LIMIT,
            "job_stale_after_seconds": JOB_STALE_AFTER_SECONDS_LIMIT,
            "database_pool_size": 100,
            "database_max_overflow": 200,
            "database_pool_recycle_seconds": 86_400,
            "auth0_jwks_cache_seconds": 86_400,
            "guest_session_ttl_seconds": 86_400,
            "guest_session_issue_requests": 1_000,
            "guest_session_issue_window_seconds": 3_600,
            "guest_max_active_sessions": 10_000,
            "guest_max_mutations_per_session": 100_000,
            "guest_max_database_bytes": 1024 * 1024 * 1024,
            "guest_max_career_identity_facts": 1_000,
            "guest_max_saved_comparisons": 1_000,
            "guest_max_decisions": 1_000,
            "guest_max_decision_options": 10_000,
            "guest_max_actions": 10_000,
            "guest_max_applications": 1_000,
            "guest_max_recommendation_snapshots": 1_000,
        }
        limit = limits.get(info.field_name)
        if limit is not None and normalized > limit:
            raise ValueError(f"value must be <= {limit}")
        return normalized

    @field_validator("database_max_overflow", mode="before")
    @classmethod
    def _validate_database_max_overflow(cls, value: int | str) -> int:
        try:
            normalized = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("DATABASE_MAX_OVERFLOW must be an integer") from exc
        if normalized < 0 or normalized > 200:
            raise ValueError("DATABASE_MAX_OVERFLOW must be between 0 and 200")
        return normalized

    @model_validator(mode="after")
    def _apply_environment_defaults(self) -> Self:
        self.release_id = self.release_id.strip() or "unknown"
        self.render_git_commit = self.render_git_commit.strip()
        if (
            self.app_env == AppEnv.PUBLIC_GUEST_DEMO
            and self.release_id == "unknown"
            and self.render_git_commit
        ):
            self.release_id = self.render_git_commit
        self.error_monitoring_dsn = self.error_monitoring_dsn.strip()

        if not self.database_url:
            if self.app_env in NON_LOCAL_ENVS:
                raise ValueError(
                    "DATABASE_URL is required when APP_ENV is private_demo, "
                    "public_demo, public_guest_demo, staging, production, dev, or prod"
                )
            self.database_url = LOCAL_DATABASE_URL

        if self.rate_limit_enabled is None:
            self.rate_limit_enabled = self.app_env in RATE_LIMIT_DEFAULT_ENABLED_ENVS
        if self.security_headers_enabled is None:
            self.security_headers_enabled = self.app_env in SECURITY_HEADERS_DEFAULT_ENABLED_ENVS
        if self.readiness_require_migration_current is None:
            self.readiness_require_migration_current = self.app_env in (
                STRICT_DEFAULT_ENABLED_ENVS | PUBLIC_GUEST_ENVS
            )
        if self.api_docs_enabled is None:
            self.api_docs_enabled = self.app_env not in (
                STRICT_DEFAULT_ENABLED_ENVS | PUBLIC_GUEST_ENVS
            )
        if self.beta_access_required is None:
            self.beta_access_required = self.app_env in STRICT_DEFAULT_ENABLED_ENVS
        if self.job_stale_after_seconds is None:
            self.job_stale_after_seconds = DEFAULT_JOB_STALE_AFTER_SECONDS
        if self.max_request_body_bytes is None:
            self.max_request_body_bytes = (
                PUBLIC_DEMO_MAX_REQUEST_BODY_BYTES
                if self.app_env in {AppEnv.PUBLIC_DEMO, AppEnv.PUBLIC_GUEST_DEMO}
                else DEFAULT_MAX_REQUEST_BODY_BYTES
            )
        if self.rate_limit_requests is None:
            self.rate_limit_requests = (
                PUBLIC_DEMO_RATE_LIMIT_REQUESTS
                if self.app_env in {AppEnv.PUBLIC_DEMO, AppEnv.PUBLIC_GUEST_DEMO}
                else DEFAULT_RATE_LIMIT_REQUESTS
            )
        if self.rate_limit_window_seconds is None:
            self.rate_limit_window_seconds = DEFAULT_RATE_LIMIT_WINDOW_SECONDS
        if self.rate_limit_anonymous_requests is None:
            self.rate_limit_anonymous_requests = self.rate_limit_requests
        if self.rate_limit_anonymous_window_seconds is None:
            self.rate_limit_anonymous_window_seconds = self.rate_limit_window_seconds
        if self.rate_limit_authenticated_requests is None:
            self.rate_limit_authenticated_requests = self.rate_limit_requests
        if self.rate_limit_authenticated_window_seconds is None:
            self.rate_limit_authenticated_window_seconds = self.rate_limit_window_seconds
        if self.rate_limit_expensive_requests is None:
            self.rate_limit_expensive_requests = min(
                int(self.rate_limit_requests),
                DEFAULT_EXPENSIVE_RATE_LIMIT_REQUESTS,
            )
        if self.rate_limit_expensive_window_seconds is None:
            self.rate_limit_expensive_window_seconds = self.rate_limit_window_seconds
        if self.rate_limit_mutation_requests is None:
            self.rate_limit_mutation_requests = min(
                int(self.rate_limit_requests),
                DEFAULT_MUTATION_RATE_LIMIT_REQUESTS,
            )
        if self.rate_limit_mutation_window_seconds is None:
            self.rate_limit_mutation_window_seconds = self.rate_limit_window_seconds

        if self.app_env == AppEnv.PUBLIC_DEMO:
            if not self.cors_allowed_origin_list:
                raise ValueError(
                    "CORS_ALLOWED_ORIGINS must list the exact public frontend "
                    "origin when APP_ENV is public_demo"
                )
            if self.rate_limit_enabled is not True:
                raise ValueError("RATE_LIMIT_ENABLED must be true when APP_ENV is public_demo")
            if self.security_headers_enabled is not True:
                raise ValueError(
                    "SECURITY_HEADERS_ENABLED must be true when APP_ENV is public_demo"
                )

        if self.app_env == AppEnv.PUBLIC_GUEST_DEMO:
            if not is_sqlite_database_url(self.database_url):
                raise ValueError(
                    "DATABASE_URL must use SQLite when APP_ENV is public_guest_demo"
                )
            derived_origin = self.public_origin or self.render_external_url
            if not derived_origin:
                raise ValueError(
                    "PUBLIC_ORIGIN or RENDER_EXTERNAL_URL is required when "
                    "APP_ENV is public_guest_demo"
                )
            if self.public_origin and self.render_external_url:
                if self.public_origin != self.render_external_url:
                    raise ValueError(
                        "PUBLIC_ORIGIN and RENDER_EXTERNAL_URL must match when both are set"
                    )
            if not derived_origin.startswith("https://"):
                raise ValueError(
                    "The public guest deployment origin must use HTTPS"
                )
            self.public_origin = derived_origin
            if self.cors_allowed_origin_list not in ([], [derived_origin]):
                raise ValueError(
                    "CORS_ALLOWED_ORIGINS must be empty or exactly PUBLIC_ORIGIN "
                    "when APP_ENV is public_guest_demo"
                )
            if self.auth0_issuer or self.auth0_audience or self.auth0_jwks_url:
                raise ValueError(
                    "Auth0 settings must be empty when APP_ENV is public_guest_demo"
                )
            if self.stripe_secret_key or self.stripe_webhook_secret:
                raise ValueError(
                    "Stripe credentials must be empty when APP_ENV is public_guest_demo"
                )
            if self.rate_limit_enabled is not True:
                raise ValueError(
                    "RATE_LIMIT_ENABLED must be true when APP_ENV is public_guest_demo"
                )
            if self.security_headers_enabled is not True:
                raise ValueError(
                    "SECURITY_HEADERS_ENABLED must be true when APP_ENV is public_guest_demo"
                )
            if self.api_docs_enabled:
                raise ValueError(
                    "API_DOCS_ENABLED must be false when APP_ENV is public_guest_demo"
                )
            if self.beta_access_required:
                raise ValueError(
                    "BETA_ACCESS_REQUIRED must be false when APP_ENV is public_guest_demo"
                )
            if not self.readiness_require_migration_current:
                raise ValueError(
                    "READINESS_REQUIRE_MIGRATION_CURRENT must be true when "
                    "APP_ENV is public_guest_demo"
                )
            if self.guest_session_ttl_seconds != 28_800:
                raise ValueError(
                    "GUEST_SESSION_TTL_SECONDS must be 28800 in public_guest_demo"
                )
            safe_guest_limits = {
                "MAX_REQUEST_BODY_BYTES": (
                    int(self.max_request_body_bytes),
                    PUBLIC_GUEST_MAX_REQUEST_BODY_BYTES,
                ),
                "RATE_LIMIT_REQUESTS": (int(self.rate_limit_requests), 60),
                "RATE_LIMIT_ANONYMOUS_REQUESTS": (
                    int(self.rate_limit_anonymous_requests),
                    60,
                ),
                "RATE_LIMIT_AUTHENTICATED_REQUESTS": (
                    int(self.rate_limit_authenticated_requests),
                    60,
                ),
                "RATE_LIMIT_EXPENSIVE_REQUESTS": (
                    int(self.rate_limit_expensive_requests),
                    20,
                ),
                "RATE_LIMIT_MUTATION_REQUESTS": (
                    int(self.rate_limit_mutation_requests),
                    60,
                ),
                "GUEST_SESSION_ISSUE_REQUESTS": (
                    self.guest_session_issue_requests,
                    10,
                ),
                "GUEST_MAX_ACTIVE_SESSIONS": (self.guest_max_active_sessions, 250),
                "GUEST_MAX_MUTATIONS_PER_SESSION": (
                    self.guest_max_mutations_per_session,
                    500,
                ),
                "GUEST_MAX_DATABASE_BYTES": (
                    self.guest_max_database_bytes,
                    64 * 1024 * 1024,
                ),
                "GUEST_MAX_CAREER_IDENTITY_FACTS": (
                    self.guest_max_career_identity_facts,
                    50,
                ),
                "GUEST_MAX_SAVED_COMPARISONS": (
                    self.guest_max_saved_comparisons,
                    25,
                ),
                "GUEST_MAX_DECISIONS": (self.guest_max_decisions, 25),
                "GUEST_MAX_DECISION_OPTIONS": (
                    self.guest_max_decision_options,
                    100,
                ),
                "GUEST_MAX_ACTIONS": (self.guest_max_actions, 100),
                "GUEST_MAX_APPLICATIONS": (self.guest_max_applications, 50),
                "GUEST_MAX_RECOMMENDATION_SNAPSHOTS": (
                    self.guest_max_recommendation_snapshots,
                    50,
                ),
            }
            for setting_name, (configured, maximum) in safe_guest_limits.items():
                if configured > maximum:
                    raise ValueError(
                        f"{setting_name} must be <= {maximum} in public_guest_demo"
                    )
            safe_guest_windows = {
                "RATE_LIMIT_WINDOW_SECONDS": int(self.rate_limit_window_seconds),
                "RATE_LIMIT_ANONYMOUS_WINDOW_SECONDS": int(
                    self.rate_limit_anonymous_window_seconds
                ),
                "RATE_LIMIT_AUTHENTICATED_WINDOW_SECONDS": int(
                    self.rate_limit_authenticated_window_seconds
                ),
                "RATE_LIMIT_EXPENSIVE_WINDOW_SECONDS": int(
                    self.rate_limit_expensive_window_seconds
                ),
                "RATE_LIMIT_MUTATION_WINDOW_SECONDS": int(
                    self.rate_limit_mutation_window_seconds
                ),
                "GUEST_SESSION_ISSUE_WINDOW_SECONDS": (
                    self.guest_session_issue_window_seconds
                ),
            }
            for setting_name, configured in safe_guest_windows.items():
                if configured < 60:
                    raise ValueError(
                        f"{setting_name} must be >= 60 in public_guest_demo"
                    )
            if self.release_id == "unknown":
                raise ValueError(
                    "RELEASE_ID is required when APP_ENV is public_guest_demo"
                )

        if self.app_env in STRICT_DEFAULT_ENABLED_ENVS:
            if is_sqlite_database_url(self.database_url):
                raise ValueError(
                    "DATABASE_URL must not use SQLite when APP_ENV is staging, production, or prod"
                )
            if self.rate_limit_enabled is not True:
                raise ValueError(
                    "RATE_LIMIT_ENABLED must be true when APP_ENV is staging, production, or prod"
                )
            if self.security_headers_enabled is not True:
                raise ValueError(
                    "SECURITY_HEADERS_ENABLED must be true when APP_ENV is staging, "
                    "production, or prod"
                )
            if not self.cors_allowed_origin_list:
                raise ValueError(
                    "CORS_ALLOWED_ORIGINS must list the exact frontend origin when "
                    "APP_ENV is staging, production, or prod"
                )
            if any(not origin.startswith("https://") for origin in self.cors_allowed_origin_list):
                raise ValueError(
                    "CORS_ALLOWED_ORIGINS must use HTTPS when APP_ENV is staging, "
                    "production, or prod"
                )
            if not self.auth0_issuer or not self.auth0_audience:
                raise ValueError(
                    "AUTH0_ISSUER and AUTH0_AUDIENCE are required when APP_ENV is "
                    "staging, production, or prod"
                )
            if self.release_id == "unknown":
                raise ValueError(
                    "RELEASE_ID is required when APP_ENV is staging, production, or prod"
                )
            if self.api_docs_enabled:
                raise ValueError(
                    "API_DOCS_ENABLED must be false when APP_ENV is staging, production, or prod"
                )
        return self

    @property
    def cors_allowed_origin_list(self) -> list[str]:
        return list(_parse_cors_allowed_origins(self.cors_allowed_origins))

    @property
    def is_public_demo_read_only(self) -> bool:
        return self.app_env in PUBLIC_DEMO_READ_ONLY_ENVS

    @property
    def is_public_guest_demo(self) -> bool:
        return self.app_env in PUBLIC_GUEST_ENVS


def _parse_cors_allowed_origins(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()

    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            raw_origins: list[Any] = []
        elif cleaned.startswith("["):
            try:
                parsed = json.loads(cleaned)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    "CORS_ALLOWED_ORIGINS must be comma-separated origins or a JSON list"
                ) from exc
            if not isinstance(parsed, list):
                raise ValueError("CORS_ALLOWED_ORIGINS JSON value must be a list")
            raw_origins = parsed
        else:
            raw_origins = cleaned.split(",")
    elif isinstance(value, list | tuple):
        raw_origins = list(value)
    else:
        raise ValueError("CORS_ALLOWED_ORIGINS must be a string or list")

    origins: list[str] = []
    seen: set[str] = set()
    for origin in raw_origins:
        if not isinstance(origin, str):
            raise ValueError("CORS_ALLOWED_ORIGINS entries must be strings")
        normalized = _normalize_cors_origin(origin)
        if normalized and normalized not in seen:
            origins.append(normalized)
            seen.add(normalized)
    return tuple(origins)


def _normalize_cors_origin(origin: str) -> str:
    normalized = origin.strip()
    if not normalized:
        return ""
    if "*" in normalized:
        raise ValueError(
            "CORS_ALLOWED_ORIGINS must list exact origins; wildcard '*' is not allowed"
        )

    parsed = urlsplit(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("CORS_ALLOWED_ORIGINS entries must be HTTP(S) origins")
    if parsed.username or parsed.password:
        raise ValueError("CORS_ALLOWED_ORIGINS entries must not include credentials")
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise ValueError("CORS_ALLOWED_ORIGINS entries must be exact origins")

    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), "", "", ""))


def _validate_external_redirect_url(url: str) -> None:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Stripe redirect URL settings must be HTTP(S) URLs")
    if parsed.username or parsed.password:
        raise ValueError("Stripe redirect URL settings must not include credentials")
    if parsed.fragment:
        raise ValueError("Stripe redirect URL settings must not include fragments")


def redact_database_url(database_url: str) -> str:
    """Render a database URL without exposing credentials."""
    if not database_url:
        return "<empty database url>"
    try:
        return make_url(database_url).render_as_string(hide_password=True)
    except Exception:
        return "<invalid database url>"


def is_sqlite_database_url(database_url: str) -> bool:
    try:
        return make_url(database_url).drivername.startswith("sqlite")
    except Exception:
        return False


@lru_cache
def get_settings() -> Settings:
    return Settings()
