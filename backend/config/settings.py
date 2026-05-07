from functools import lru_cache

from pydantic import Field
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


@lru_cache
def get_settings() -> Settings:
    return Settings()
