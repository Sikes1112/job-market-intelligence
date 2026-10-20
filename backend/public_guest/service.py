from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import delete, func, select, update
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from backend.auth.boundary import ExternalAuthPrincipal
from backend.config.settings import Settings
from backend.public_guest.models import PublicGuestSession
from backend.users.repository import UserRepository
from backend.users.service import UserIdentityService

PUBLIC_GUEST_PROVIDER = "public_guest"
PUBLIC_GUEST_ISSUER = "urn:jmi:public-guest"
PUBLIC_GUEST_COOKIE_NAME = "__Host-jmi_guest"
PUBLIC_GUEST_CSRF_HEADER = "x-csrf-token"
SESSION_TOKEN_BYTES = 32
CSRF_TOKEN_BYTES = 32


class GuestSessionCapacityExceeded(RuntimeError):
    pass


class GuestDatabaseCapacityExceeded(RuntimeError):
    pass


class GuestMutationQuotaExceeded(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class VerifiedGuestPrincipal:
    session_id: str
    user_id: str
    provider: str
    issuer: str
    subject: str
    expires_at: datetime

    def as_external_principal(self) -> ExternalAuthPrincipal:
        return ExternalAuthPrincipal(
            provider=self.provider,
            issuer=self.issuer,
            subject=self.subject,
        )


@dataclass(frozen=True, slots=True)
class GuestSessionBootstrap:
    session_token: str
    csrf_token: str
    principal: VerifiedGuestPrincipal
    created: bool


class PublicGuestSessionService:
    def __init__(self, session: Session, settings: Settings) -> None:
        self._session = session
        self._settings = settings

    def bootstrap(self, presented_token: str | None) -> GuestSessionBootstrap:
        now = datetime.now(UTC)
        self.cleanup_expired(now=now)
        self._ensure_database_capacity()

        existing = self.resolve(presented_token, now=now, touch=False)
        if existing is not None and presented_token is not None:
            csrf_token = _new_credential()
            row = self._session.get(PublicGuestSession, existing.session_id)
            if row is None:
                # The row could only disappear through a concurrent reset.
                return self._create(now)
            row.csrf_token_digest = credential_digest(csrf_token)
            row.last_seen_at = now
            self._session.flush()
            return GuestSessionBootstrap(
                session_token=presented_token,
                csrf_token=csrf_token,
                principal=_principal(row),
                created=False,
            )

        return self._create(now)

    def resolve(
        self,
        presented_token: str | None,
        *,
        now: datetime | None = None,
        touch: bool = True,
    ) -> VerifiedGuestPrincipal | None:
        if not _credential_shape_valid(presented_token):
            return None
        current_time = now or datetime.now(UTC)
        digest = credential_digest(presented_token)
        row = self._session.scalar(
            select(PublicGuestSession).where(
                PublicGuestSession.token_digest == digest
            )
        )
        if row is None or row.revoked_at is not None:
            return None
        if _as_utc(row.expires_at) <= current_time:
            return None
        if not secrets.compare_digest(row.token_digest, digest):
            return None
        if touch:
            row.last_seen_at = current_time
            self._session.flush()
        return _principal(row)

    def csrf_valid(self, session_id: str, presented_token: str | None) -> bool:
        if not _credential_shape_valid(presented_token):
            return False
        row = self._session.get(PublicGuestSession, session_id)
        if row is None or row.revoked_at is not None:
            return False
        if _as_utc(row.expires_at) <= datetime.now(UTC):
            return False
        return secrets.compare_digest(
            row.csrf_token_digest,
            credential_digest(presented_token),
        )

    def consume_mutation(self, session_id: str) -> None:
        self._ensure_database_capacity()
        result = self._session.execute(
            update(PublicGuestSession)
            .where(
                PublicGuestSession.session_id == session_id,
                PublicGuestSession.revoked_at.is_(None),
                PublicGuestSession.mutation_count
                < self._settings.guest_max_mutations_per_session,
            )
            .values(mutation_count=PublicGuestSession.mutation_count + 1)
        )
        if result.rowcount != 1:
            raise GuestMutationQuotaExceeded("guest mutation quota reached")

    def cleanup_expired(self, *, now: datetime | None = None) -> int:
        current_time = now or datetime.now(UTC)
        result = self._session.execute(
            delete(PublicGuestSession).where(
                (PublicGuestSession.expires_at <= current_time)
                | (PublicGuestSession.revoked_at.is_not(None))
            )
        )
        return int(result.rowcount or 0)

    def _create(self, now: datetime) -> GuestSessionBootstrap:
        active_count = self._session.scalar(
            select(func.count())
            .select_from(PublicGuestSession)
            .where(
                PublicGuestSession.revoked_at.is_(None),
                PublicGuestSession.expires_at > now,
            )
        )
        if int(active_count or 0) >= self._settings.guest_max_active_sessions:
            raise GuestSessionCapacityExceeded("guest session capacity reached")

        session_token = _new_credential()
        csrf_token = _new_credential()
        subject = f"guest_{secrets.token_hex(24)}"
        resolved = UserIdentityService(UserRepository(self._session)).resolve_external_principal(
            ExternalAuthPrincipal(
                provider=PUBLIC_GUEST_PROVIDER,
                issuer=PUBLIC_GUEST_ISSUER,
                subject=subject,
            )
        )
        row = PublicGuestSession(
            session_id=f"guest_session_{secrets.token_hex(20)}",
            user_id=resolved.user.user_id,
            subject=subject,
            token_digest=credential_digest(session_token),
            csrf_token_digest=credential_digest(csrf_token),
            mutation_count=0,
            created_at=now,
            last_seen_at=now,
            expires_at=now + timedelta(seconds=self._settings.guest_session_ttl_seconds),
        )
        self._session.add(row)
        self._session.flush()
        return GuestSessionBootstrap(
            session_token=session_token,
            csrf_token=csrf_token,
            principal=_principal(row),
            created=True,
        )

    def _ensure_database_capacity(self) -> None:
        size = sqlite_database_size_bytes(self._settings.database_url)
        if size is not None and size >= self._settings.guest_max_database_bytes:
            raise GuestDatabaseCapacityExceeded("guest database capacity reached")


def credential_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def sqlite_database_size_bytes(database_url: str) -> int | None:
    url = make_url(database_url)
    if not url.drivername.startswith("sqlite") or not url.database or url.database == ":memory:":
        return None
    path = Path(url.database)
    return sum(
        candidate.stat().st_size
        for candidate in (path, Path(f"{path}-wal"), Path(f"{path}-shm"))
        if candidate.exists()
    )


def _new_credential() -> str:
    return secrets.token_urlsafe(SESSION_TOKEN_BYTES)


def _credential_shape_valid(token: str | None) -> bool:
    return isinstance(token, str) and 40 <= len(token) <= 64


def _principal(row: PublicGuestSession) -> VerifiedGuestPrincipal:
    return VerifiedGuestPrincipal(
        session_id=row.session_id,
        user_id=row.user_id,
        provider=PUBLIC_GUEST_PROVIDER,
        issuer=PUBLIC_GUEST_ISSUER,
        subject=row.subject,
        expires_at=_as_utc(row.expires_at),
    )


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
