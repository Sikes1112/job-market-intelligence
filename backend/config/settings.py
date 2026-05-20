import json
from enum import StrEnum
from functools import lru_cache
from typing import Any, Self
from urllib.parse import urlsplit, urlunsplit

from pydantic import Field, ValidationInfo, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


class AppEnv(StrEnum):
    LOCAL = "local"
    TEST = "test"
    DEV = "dev"
    STAGING = "staging"
    PROD = "prod"


LOCAL_DATABASE_URL = "sqlite:///./jmi.db"
LOG_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})
NON_LOCAL_ENVS = frozenset({AppEnv.DEV, AppEnv.STAGING, AppEnv.PROD})
STRICT_DEFAULT_ENABLED_ENVS = frozenset({AppEnv.STAGING, AppEnv.PROD})
MAX_REQUEST_BODY_BYTES_LIMIT = 10 * 1024 * 1024
RATE_LIMIT_REQUESTS_LIMIT = 10_000
RATE_LIMIT_WINDOW_SECONDS_LIMIT = 3_600


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
    database_url: str = Field(default="", repr=False)
    cors_allowed_origins: str = Field(default="")
    rate_limit_enabled: bool | None = Field(default=None)
    security_headers_enabled: bool | None = Field(default=None)
    max_request_body_bytes: int = Field(default=1_048_576)
    rate_limit_requests: int = Field(default=120)
    rate_limit_window_seconds: int = Field(default=60)

    @field_validator("app_env", mode="before")
    @classmethod
    def _normalize_app_env(cls, value: AppEnv | str) -> AppEnv | str:
        if isinstance(value, str):
            return value.strip().lower()
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

    @field_validator("cors_allowed_origins", mode="before")
    @classmethod
    def _normalize_cors_allowed_origins(cls, value: Any) -> str:
        origins = _parse_cors_allowed_origins(value)
        if any("*" in origin for origin in origins):
            raise ValueError(
                "CORS_ALLOWED_ORIGINS must list exact origins; wildcard '*' is not allowed"
            )
        return ",".join(origins)

    @field_validator("rate_limit_enabled", "security_headers_enabled", mode="before")
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
    )
    @classmethod
    def _validate_positive_int(cls, value: int, info: ValidationInfo) -> int:
        if value < 1:
            raise ValueError("value must be >= 1")
        limits = {
            "max_request_body_bytes": MAX_REQUEST_BODY_BYTES_LIMIT,
            "rate_limit_requests": RATE_LIMIT_REQUESTS_LIMIT,
            "rate_limit_window_seconds": RATE_LIMIT_WINDOW_SECONDS_LIMIT,
        }
        limit = limits.get(info.field_name)
        if limit is not None and value > limit:
            raise ValueError(f"value must be <= {limit}")
        return value

    @model_validator(mode="after")
    def _apply_environment_defaults(self) -> Self:
        if not self.database_url:
            if self.app_env in NON_LOCAL_ENVS:
                raise ValueError(
                    "DATABASE_URL is required when APP_ENV is dev, staging, or prod"
                )
            self.database_url = LOCAL_DATABASE_URL

        if self.rate_limit_enabled is None:
            self.rate_limit_enabled = self.app_env in STRICT_DEFAULT_ENABLED_ENVS
        if self.security_headers_enabled is None:
            self.security_headers_enabled = self.app_env in STRICT_DEFAULT_ENABLED_ENVS

        if self.app_env in STRICT_DEFAULT_ENABLED_ENVS:
            if is_sqlite_database_url(self.database_url):
                raise ValueError(
                    "DATABASE_URL must not use SQLite when APP_ENV is staging or prod"
                )
            if self.rate_limit_enabled is not True:
                raise ValueError(
                    "RATE_LIMIT_ENABLED must be true when APP_ENV is staging or prod"
                )
            if self.security_headers_enabled is not True:
                raise ValueError(
                    "SECURITY_HEADERS_ENABLED must be true when APP_ENV is staging or prod"
                )
        return self

    @property
    def cors_allowed_origin_list(self) -> list[str]:
        return list(_parse_cors_allowed_origins(self.cors_allowed_origins))


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
