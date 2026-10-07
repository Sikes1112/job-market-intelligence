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
        AppEnv.STAGING,
        AppEnv.PRODUCTION,
        AppEnv.DEV,
        AppEnv.PROD,
    }
)
STRICT_DEFAULT_ENABLED_ENVS = frozenset(
    {AppEnv.STAGING, AppEnv.PRODUCTION, AppEnv.PROD}
)
PUBLIC_DEMO_READ_ONLY_ENVS = frozenset({AppEnv.PUBLIC_DEMO})
RATE_LIMIT_DEFAULT_ENABLED_ENVS = STRICT_DEFAULT_ENABLED_ENVS | PUBLIC_DEMO_READ_ONLY_ENVS
SECURITY_HEADERS_DEFAULT_ENABLED_ENVS = (
    STRICT_DEFAULT_ENABLED_ENVS | PUBLIC_DEMO_READ_ONLY_ENVS
)
DEFAULT_MAX_REQUEST_BODY_BYTES = 1_048_576
PUBLIC_DEMO_MAX_REQUEST_BODY_BYTES = 65_536
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
    database_url: str = Field(default="", repr=False)
    cors_allowed_origins: str = Field(default="")
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

    @field_validator(
        "rate_limit_enabled",
        "security_headers_enabled",
        "readiness_require_migration_current",
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
            "auth0_jwks_cache_seconds": 86_400,
        }
        limit = limits.get(info.field_name)
        if limit is not None and normalized > limit:
            raise ValueError(f"value must be <= {limit}")
        return normalized

    @model_validator(mode="after")
    def _apply_environment_defaults(self) -> Self:
        self.release_id = self.release_id.strip() or "unknown"
        self.error_monitoring_dsn = self.error_monitoring_dsn.strip()

        if not self.database_url:
            if self.app_env in NON_LOCAL_ENVS:
                raise ValueError(
                    "DATABASE_URL is required when APP_ENV is private_demo, "
                    "public_demo, staging, production, dev, or prod"
                )
            self.database_url = LOCAL_DATABASE_URL

        if self.rate_limit_enabled is None:
            self.rate_limit_enabled = self.app_env in RATE_LIMIT_DEFAULT_ENABLED_ENVS
        if self.security_headers_enabled is None:
            self.security_headers_enabled = self.app_env in SECURITY_HEADERS_DEFAULT_ENABLED_ENVS
        if self.readiness_require_migration_current is None:
            self.readiness_require_migration_current = (
                self.app_env in STRICT_DEFAULT_ENABLED_ENVS
            )
        if self.job_stale_after_seconds is None:
            self.job_stale_after_seconds = DEFAULT_JOB_STALE_AFTER_SECONDS
        if self.max_request_body_bytes is None:
            self.max_request_body_bytes = (
                PUBLIC_DEMO_MAX_REQUEST_BODY_BYTES
                if self.app_env == AppEnv.PUBLIC_DEMO
                else DEFAULT_MAX_REQUEST_BODY_BYTES
            )
        if self.rate_limit_requests is None:
            self.rate_limit_requests = (
                PUBLIC_DEMO_RATE_LIMIT_REQUESTS
                if self.app_env == AppEnv.PUBLIC_DEMO
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
                raise ValueError(
                    "RATE_LIMIT_ENABLED must be true when APP_ENV is public_demo"
                )
            if self.security_headers_enabled is not True:
                raise ValueError(
                    "SECURITY_HEADERS_ENABLED must be true when APP_ENV is public_demo"
                )

        if self.app_env in STRICT_DEFAULT_ENABLED_ENVS:
            if is_sqlite_database_url(self.database_url):
                raise ValueError(
                    "DATABASE_URL must not use SQLite when APP_ENV is staging, "
                    "production, or prod"
                )
            if self.rate_limit_enabled is not True:
                raise ValueError(
                    "RATE_LIMIT_ENABLED must be true when APP_ENV is staging, "
                    "production, or prod"
                )
            if self.security_headers_enabled is not True:
                raise ValueError(
                    "SECURITY_HEADERS_ENABLED must be true when APP_ENV is staging, "
                    "production, or prod"
                )
        return self

    @property
    def cors_allowed_origin_list(self) -> list[str]:
        return list(_parse_cors_allowed_origins(self.cors_allowed_origins))

    @property
    def is_public_demo_read_only(self) -> bool:
        return self.app_env in PUBLIC_DEMO_READ_ONLY_ENVS


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
