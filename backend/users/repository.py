"""Thin data-access layer for internal app-user identity tables."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.alerts.models import UserAlert
from backend.career_agent.models import (
    CareerAgentToolAuditEventRecord,
    CareerAgentToolRecord,
    CareerMemoryEntryRecord,
    CareerMemoryPermissionRecord,
)
from backend.users.models import (
    ExternalAuthIdentity,
    PersonalizedRecommendationSnapshot,
    SavedMarketArtifact,
    User,
    UserPreferenceProfile,
    UserProfile,
)


class UserRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_user(self, user_id: str) -> User | None:
        return self._session.get(User, user_id)

    def get_profile(self, user_id: str) -> UserProfile | None:
        return self._session.get(UserProfile, user_id)

    def list_external_identities(self, user_id: str) -> list[ExternalAuthIdentity]:
        rows = self._session.execute(
            select(ExternalAuthIdentity)
            .where(ExternalAuthIdentity.user_id == user_id)
            .order_by(
                ExternalAuthIdentity.provider,
                ExternalAuthIdentity.issuer,
                ExternalAuthIdentity.subject,
                ExternalAuthIdentity.external_identity_id,
            )
        ).scalars()
        return list(rows)

    def get_preference_profile(self, user_id: str) -> UserPreferenceProfile | None:
        return self._session.get(UserPreferenceProfile, user_id)

    def get_external_identity(
        self,
        *,
        provider: str,
        issuer: str,
        subject: str,
    ) -> ExternalAuthIdentity | None:
        row = self._session.execute(
            select(ExternalAuthIdentity).where(
                ExternalAuthIdentity.provider == provider,
                ExternalAuthIdentity.issuer == issuer,
                ExternalAuthIdentity.subject == subject,
            )
        ).scalar_one_or_none()
        return row

    def add_user(self, user: User) -> None:
        self._session.add(user)

    def add_external_identity(self, identity: ExternalAuthIdentity) -> None:
        self._session.add(identity)

    def add_profile(self, profile: UserProfile) -> None:
        self._session.add(profile)

    def add_preference_profile(self, profile: UserPreferenceProfile) -> None:
        self._session.add(profile)

    def get_saved_market_artifact(
        self, saved_artifact_id: str
    ) -> SavedMarketArtifact | None:
        return self._session.get(SavedMarketArtifact, saved_artifact_id)

    def list_saved_market_artifacts(
        self,
        *,
        user_id: str,
        artifact_type: str | None = None,
    ) -> list[SavedMarketArtifact]:
        stmt = select(SavedMarketArtifact).where(SavedMarketArtifact.user_id == user_id)
        if artifact_type is not None:
            stmt = stmt.where(SavedMarketArtifact.artifact_type == artifact_type)
        rows = self._session.execute(
            stmt.order_by(
                SavedMarketArtifact.created_at,
                SavedMarketArtifact.saved_artifact_id,
            )
        ).scalars()
        return list(rows)

    def add_saved_market_artifact(self, artifact: SavedMarketArtifact) -> None:
        self._session.add(artifact)

    def delete_saved_market_artifact(self, artifact: SavedMarketArtifact) -> None:
        self._session.delete(artifact)

    def delete_saved_market_artifacts_for_user(self, user_id: str) -> int:
        artifacts = self.list_saved_market_artifacts(user_id=user_id)
        for artifact in artifacts:
            self._session.delete(artifact)
        return len(artifacts)

    def add_recommendation_snapshot(
        self,
        snapshot: PersonalizedRecommendationSnapshot,
    ) -> None:
        self._session.add(snapshot)

    def get_recommendation_snapshot(
        self,
        recommendation_snapshot_id: str,
    ) -> PersonalizedRecommendationSnapshot | None:
        return self._session.get(
            PersonalizedRecommendationSnapshot,
            recommendation_snapshot_id,
        )

    def list_recommendation_snapshots(
        self,
        *,
        user_id: str,
    ) -> list[PersonalizedRecommendationSnapshot]:
        rows = self._session.execute(
            select(PersonalizedRecommendationSnapshot)
            .where(PersonalizedRecommendationSnapshot.user_id == user_id)
            .order_by(
                PersonalizedRecommendationSnapshot.generated_at.desc(),
                PersonalizedRecommendationSnapshot.recommendation_snapshot_id,
            )
        ).scalars()
        return list(rows)

    def list_user_alerts_for_user(self, user_id: str) -> list[UserAlert]:
        rows = self._session.execute(
            select(UserAlert)
            .where(UserAlert.user_id == user_id)
            .order_by(UserAlert.created_at, UserAlert.user_alert_id)
        ).scalars()
        return list(rows)

    def delete_user_alerts_for_user(self, user_id: str) -> int:
        alerts = self.list_user_alerts_for_user(user_id)
        for alert in alerts:
            self._session.delete(alert)
        return len(alerts)

    def delete_career_memory_for_user(self, user_id: str) -> int:
        entry_rows = list(
            self._session.execute(
                select(CareerMemoryEntryRecord).where(
                    CareerMemoryEntryRecord.user_id == user_id
                )
            ).scalars()
        )
        permission_rows = list(
            self._session.execute(
                select(CareerMemoryPermissionRecord).where(
                    CareerMemoryPermissionRecord.user_id == user_id
                )
            ).scalars()
        )
        for row in (*entry_rows, *permission_rows):
            self._session.delete(row)
        return len(entry_rows) + len(permission_rows)

    def delete_career_agent_tool_records_for_user(self, user_id: str) -> int:
        audit_rows = list(
            self._session.execute(
                select(CareerAgentToolAuditEventRecord).where(
                    CareerAgentToolAuditEventRecord.user_id == user_id
                )
            ).scalars()
        )
        tool_rows = list(
            self._session.execute(
                select(CareerAgentToolRecord).where(
                    CareerAgentToolRecord.user_id == user_id
                )
            ).scalars()
        )
        for row in (*audit_rows, *tool_rows):
            self._session.delete(row)
        return len(audit_rows) + len(tool_rows)

    def clear_snapshot_preference_profile_for_user(self, user_id: str) -> int:
        snapshots = self._session.execute(
            select(PersonalizedRecommendationSnapshot).where(
                PersonalizedRecommendationSnapshot.user_id == user_id,
                PersonalizedRecommendationSnapshot.preference_profile_id == user_id,
            )
        ).scalars()
        count = 0
        for snapshot in snapshots:
            snapshot.preference_profile_id = None
            count += 1
        return count

    def delete_recommendation_snapshots_for_user(self, user_id: str) -> int:
        snapshots = self.list_recommendation_snapshots(user_id=user_id)
        for snapshot in snapshots:
            self._session.delete(snapshot)
        return len(snapshots)

    def delete_preference_profile(self, profile: UserPreferenceProfile) -> None:
        self._session.delete(profile)

    def delete_profile(self, profile: UserProfile) -> None:
        self._session.delete(profile)

    def delete_external_identities_for_user(self, user_id: str) -> int:
        identities = self.list_external_identities(user_id)
        for identity in identities:
            self._session.delete(identity)
        return len(identities)

    def flush(self) -> None:
        self._session.flush()
