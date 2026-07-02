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


def _normalize_database_url(database_url: str) -> str:
    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql+psycopg://", 1)
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    return database_url


def make_engine(database_url: str, *, echo: bool = False) -> Engine:
    is_sqlite = database_url.startswith("sqlite")
    engine_url = _normalize_database_url(database_url)
    connect_args: dict = {}
    poolclass = None
    if is_sqlite:
        connect_args["check_same_thread"] = False
        # In-memory SQLite databases are per-connection by default. Tests
        # (and the API layer sharing a session via dependency overrides)
        # need every connection to see the same data, so pin a single
        # shared connection via StaticPool.
        if ":memory:" in database_url or database_url == "sqlite://":
            from sqlalchemy.pool import StaticPool

            poolclass = StaticPool
    engine_kwargs = {
        "echo": echo,
        "future": True,
        "connect_args": connect_args,
    }
    if poolclass is not None:
        engine_kwargs["poolclass"] = poolclass
    if not is_sqlite:
        engine_kwargs["pool_pre_ping"] = True

    engine = create_engine(engine_url, **engine_kwargs)
    if is_sqlite:
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


def import_all_models() -> None:
    """Register every canonical SQLAlchemy model with ``Base.metadata``."""
    # Importing every domain models module registers its mappers with
    # Base.metadata. Keep this list in sync as canonical entities are added.
    from backend.admin import models as _admin  # noqa: F401
    from backend.alerts import models as _alerts  # noqa: F401
    from backend.billing import models as _billing  # noqa: F401
    from backend.companies import models as _companies  # noqa: F401
    from backend.entry_level import models as _entry_level  # noqa: F401
    from backend.geography import models as _geography  # noqa: F401
    from backend.hiring import models as _hiring  # noqa: F401
    from backend.ingestion import models as _ingestion  # noqa: F401
    from backend.institutions import models as _institutions  # noqa: F401
    from backend.integrations import models as _integrations  # noqa: F401
    from backend.monetization import models as _monetization  # noqa: F401
    from backend.orchestration.jobs import models as _jobs  # noqa: F401
    from backend.outputs import models as _outputs  # noqa: F401
    from backend.platform import models as _platform  # noqa: F401
    from backend.platform_intelligence import models as _platform_intelligence  # noqa: F401
    from backend.presence import models as _presence  # noqa: F401
    from backend.provenance import models as _provenance  # noqa: F401
    from backend.region_expansion import models as _region_expansion  # noqa: F401
    from backend.scoring import models as _scoring  # noqa: F401
    from backend.users import models as _users  # noqa: F401


def create_all(engine: Engine) -> None:
    """Demo/test-only schema helper.

    Production-operable schema creation now goes through Alembic migrations.
    This helper remains for narrow in-memory tests and legacy local demo paths.
    """
    import_all_models()
    Base.metadata.create_all(engine)
