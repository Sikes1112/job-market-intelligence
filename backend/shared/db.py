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
    validates,
)

from backend.shared.state import ObjectState


class Base(DeclarativeBase):
    pass


class CanonicalMixin:
    """Shared metadata fields carried by every canonical truth and output object.

    State strings are validated against :class:`ObjectState` (Slice 3). Transition
    validation between states still belongs in calling code via
    :func:`backend.shared.state.validate_transition` — the column validator only
    rejects values outside the MVP enum.

    Version is a monotonically increasing integer; rendering as ``v{n}`` is a
    presentation detail (see :mod:`backend.shared.versioning`).
    """

    state: Mapped[str] = mapped_column(
        String(32), nullable=False, default=ObjectState.NEW.value
    )
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

    @validates("state")
    def _validate_state(self, _key: str, value: ObjectState | str) -> str:
        if isinstance(value, ObjectState):
            return value.value
        if not isinstance(value, str) or value not in ObjectState.values():
            raise ValueError(f"invalid object state: {value!r}")
        return value


def make_engine(database_url: str, *, echo: bool = False) -> Engine:
    connect_args: dict = {}
    poolclass = None
    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
        # In-memory SQLite databases are per-connection by default. Tests
        # (and the API layer sharing a session via dependency overrides)
        # need every connection to see the same data, so pin a single
        # shared connection via StaticPool.
        if ":memory:" in database_url or database_url == "sqlite://":
            from sqlalchemy.pool import StaticPool

            poolclass = StaticPool
    engine = create_engine(
        database_url,
        echo=echo,
        future=True,
        connect_args=connect_args,
        **({"poolclass": poolclass} if poolclass is not None else {}),
    )
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
