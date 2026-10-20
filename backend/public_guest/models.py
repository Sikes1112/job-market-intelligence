from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.db import Base


def _utc_now() -> datetime:
    return datetime.now(UTC)


class PublicGuestSession(Base):
    """Opaque, revocable browser session for the public guest sandbox.

    Raw session and CSRF credentials are never stored. The internal user is
    still the ownership authority for application records; this row only maps
    a verified browser credential to that user.
    """

    __tablename__ = "public_guest_sessions"
    __table_args__ = (
        Index("ix_public_guest_sessions_user", "user_id"),
        Index("ix_public_guest_sessions_expires", "expires_at"),
        Index("ix_public_guest_sessions_active", "revoked_at", "expires_at"),
    )

    session_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("users.user_id"), nullable=False, unique=True
    )
    subject: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    token_digest: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    csrf_token_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    mutation_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
