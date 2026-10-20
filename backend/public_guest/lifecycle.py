from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.engine import Engine

from backend.config.settings import Settings
from backend.shared.db import make_session_factory, session_scope
from backend.shared.migrations import upgrade_database
from backend.users.models import ExternalAuthIdentity
from seeds.mvp_seed import run_seed
from seeds.portfolio_seed import run_portfolio_seed
from seeds.reviewer_scenarios import LOCAL_DEMO_ISSUER, LOCAL_DEMO_SUBJECT


def initialize_public_guest_database(settings: Settings, engine: Engine) -> None:
    """Migrate and idempotently seed the ephemeral public guest database."""

    if not settings.is_public_guest_demo:
        return
    upgrade_database(settings.database_url)
    now = datetime.now(UTC)
    factory = make_session_factory(engine)
    with session_scope(factory) as session:
        seed_result = run_seed(session, demo_now=now)
        run_portfolio_seed(
            session,
            seed_result,
            as_of=now.date(),
            demo_now=now,
            include_reviewer=False,
        )
        shared_reviewer = session.scalar(
            select(ExternalAuthIdentity).where(
                ExternalAuthIdentity.issuer == LOCAL_DEMO_ISSUER,
                ExternalAuthIdentity.subject == LOCAL_DEMO_SUBJECT,
            )
        )
        if shared_reviewer is not None:
            raise RuntimeError(
                "public guest database contains the shared local reviewer identity"
            )
