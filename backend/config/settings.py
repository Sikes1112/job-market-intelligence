from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = Field(default="dev")
    log_level: str = Field(default="INFO")
    service_name: str = Field(default="jmi-backend")
    database_url: str = Field(default="sqlite:///./jmi.db")
    cors_allowed_origins: str = Field(default="")

    @field_validator("cors_allowed_origins")
    @classmethod
    def _reject_wildcard_cors(cls, value: str) -> str:
        origins = [origin.strip() for origin in value.split(",") if origin.strip()]
        if any("*" in origin for origin in origins):
            raise ValueError(
                "CORS_ALLOWED_ORIGINS must list exact origins; wildcard '*' is not allowed"
            )
        return value

    @property
    def cors_allowed_origin_list(self) -> list[str]:
        origins: list[str] = []
        seen: set[str] = set()
        for origin in self.cors_allowed_origins.split(","):
            cleaned = origin.strip()
            if cleaned and cleaned not in seen:
                origins.append(cleaned)
                seen.add(cleaned)
        return origins


@lru_cache
def get_settings() -> Settings:
    return Settings()
