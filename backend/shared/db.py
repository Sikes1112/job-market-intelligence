from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime

from sqlalchemy import DateTime, Engine, Integer, String, create_engine, event
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    sessionmaker,
)


class Base(DeclarativeBase):
    pass


class CanonicalMixin:
    """Shared metadata fields carried by every canonical truth and output object.

    State is a plain string here. Transition validation belongs to Slice 3.
    Version is a monotonically increasing integer; rendering as ``v{n}`` is a
    presentation detail.
    """

    state: Mapped[str] = mapped_column(String(32), nullable=False, default="new")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


def make_engine(database_url: str, *, echo: bool = False) -> Engine:
    connect_args: dict = {}
    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    engine = create_engine(database_url, echo=echo, future=True, connect_args=connect_args)
    if database_url.startswith("sqlite"):
        # SQLite ignores FOREIGN KEY constraints unless explicitly enabled per
        # connection. Match the behavior of a real RDBMS.
        @event.listens_for(engine, "connect")
        def _enforce_sqlite_foreign_keys(dbapi_connection, _connection_record):  # noqa: ANN001
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


@contextmanager
def session_scope(session_factory: sessionmaker[Session]) -> Iterator[Session]:
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def create_all(engine: Engine) -> None:
    """Create every registered table.

    This is the MVP "equivalent persistence setup" called out in SLICE_PLAN.md
    Slice 2 success criteria. Alembic remains an option for future schema
    evolution, but the canonical schema is locked at this slice.
    """
    # Importing every domain models module registers its mappers with
    # Base.metadata. Keep this list in sync as canonical entities are added.
    from backend.companies import models as _companies  # noqa: F401
    from backend.entry_level import models as _entry_level  # noqa: F401
    from backend.geography import models as _geography  # noqa: F401
    from backend.hiring import models as _hiring  # noqa: F401
    from backend.orchestration.jobs import models as _jobs  # noqa: F401
    from backend.outputs import models as _outputs  # noqa: F401
    from backend.presence import models as _presence  # noqa: F401
    from backend.scoring import models as _scoring  # noqa: F401

    Base.metadata.create_all(engine)
