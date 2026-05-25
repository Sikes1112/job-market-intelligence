from __future__ import annotations

import os
from typing import NoReturn

from backend.config.settings import AppEnv, Settings, is_sqlite_database_url

ALLOW_NON_LOCAL_DEMO_DB_ENV = "JMI_ALLOW_NON_LOCAL_DEMO_DB"
SCRIPT_BLOCKED_ENVS = frozenset(
    {AppEnv.PUBLIC_DEMO, AppEnv.STAGING, AppEnv.PRODUCTION, AppEnv.PROD}
)


def ensure_demo_database_target_allowed(settings: Settings, database_url: str) -> None:
    """Fail closed before local/demo scripts can target production-like DBs."""
    if settings.app_env in SCRIPT_BLOCKED_ENVS:
        _blocked(
            "Local/demo database scripts are blocked when APP_ENV is public_demo, "
            "staging, production, or prod. "
            "Use the production migration/deployment procedure instead."
        )

    if not is_sqlite_database_url(database_url) and not _non_local_demo_db_allowed():
        _blocked(
            "Local/demo database scripts refuse non-SQLite DATABASE_URL values "
            f"unless {ALLOW_NON_LOCAL_DEMO_DB_ENV}=true is set explicitly."
        )


def _non_local_demo_db_allowed() -> bool:
    return os.getenv(ALLOW_NON_LOCAL_DEMO_DB_ENV, "").strip().lower() in {
        "1",
        "true",
        "t",
        "yes",
        "y",
        "on",
    }


def _blocked(message: str) -> NoReturn:
    raise SystemExit(message)
