"""FastAPI dependencies for the read layer.

* :func:`get_session` yields a SQLAlchemy session bound to the app's engine.
  Tests override this dependency to share their seeded session.
* :func:`get_output_service` constructs an :class:`OutputAssemblyService`
  with all required repositories + the session.

The dependencies wire only repositories and the output service. **No upstream
domain service** (companies/geography/presence/hiring/entry_level/scoring)
is constructed in the API layer — the layer-isolation test pins this.
"""

from __future__ import annotations

from collections.abc import Iterator

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from backend.companies.repository import CompanyRepository
from backend.entry_level.repository import EntryLevelRepository
from backend.geography.repository import RegionRepository
from backend.hiring.repository import HiringRepository
from backend.outputs.repository import OutputMetadataRepository
from backend.outputs.service import OutputAssemblyService
from backend.presence.repository import PresenceRepository
from backend.scoring.repository import RegionScoreRepository


def get_session(request: Request) -> Iterator[Session]:
    factory = request.app.state.session_factory
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_output_service(
    session: Session = Depends(get_session),
) -> OutputAssemblyService:
    return OutputAssemblyService(
        OutputMetadataRepository(session),
        session=session,
        region_repo=RegionRepository(session),
        company_repo=CompanyRepository(session),
        presence_repo=PresenceRepository(session),
        hiring_repo=HiringRepository(session),
        entry_level_repo=EntryLevelRepository(session),
        score_repo=RegionScoreRepository(session),
    )


def get_region_repository(
    session: Session = Depends(get_session),
) -> RegionRepository:
    return RegionRepository(session)
