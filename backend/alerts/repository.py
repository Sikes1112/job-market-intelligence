"""Repository helpers for in-app alert records."""

from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from backend.alerts.models import AlertEvent, UserAlert
from backend.users.models import SavedMarketArtifact, UserPreferenceProfile


class AlertRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add_event(self, event: AlertEvent) -> None:
        self._session.add(event)

    def get_event(self, alert_event_id: str) -> AlertEvent | None:
        return self._session.get(AlertEvent, alert_event_id)

    def list_events(self, *, limit: int = 100) -> list[AlertEvent]:
        rows = self._session.execute(
            select(AlertEvent)
            .order_by(AlertEvent.created_at.desc(), AlertEvent.alert_event_id)
            .limit(limit)
        ).scalars()
        return list(rows)

    def add_user_alert(self, alert: UserAlert) -> None:
        self._session.add(alert)

    def get_user_alert(self, user_alert_id: str) -> UserAlert | None:
        return self._session.get(UserAlert, user_alert_id)

    def get_user_alert_for_event(
        self,
        *,
        user_id: str,
        alert_event_id: str,
    ) -> UserAlert | None:
        return self._session.execute(
            select(UserAlert).where(
                UserAlert.user_id == user_id,
                UserAlert.alert_event_id == alert_event_id,
            )
        ).scalar_one_or_none()

    def list_user_alerts(
        self,
        *,
        user_id: str,
        include_dismissed: bool = False,
        limit: int = 100,
    ) -> list[tuple[UserAlert, AlertEvent]]:
        stmt = (
            select(UserAlert, AlertEvent)
            .join(AlertEvent, UserAlert.alert_event_id == AlertEvent.alert_event_id)
            .where(UserAlert.user_id == user_id)
        )
        if not include_dismissed:
            stmt = stmt.where(UserAlert.dismissed.is_(False))
        rows = self._session.execute(
            stmt.order_by(UserAlert.created_at.desc(), UserAlert.user_alert_id).limit(limit)
        )
        return list(rows)

    def list_relevance_artifacts_for_event(
        self,
        event: AlertEvent,
    ) -> list[SavedMarketArtifact]:
        predicates = []
        if event.company_id:
            predicates.append(
                (SavedMarketArtifact.artifact_type == "company")
                & (SavedMarketArtifact.artifact_ref == event.company_id)
            )
        if event.region_id:
            predicates.append(
                (SavedMarketArtifact.artifact_type == "region")
                & (SavedMarketArtifact.artifact_ref == event.region_id)
            )
            predicates.append(SavedMarketArtifact.artifact_type == "comparison")
        if event.role_family:
            predicates.append(
                (SavedMarketArtifact.artifact_type == "role_family")
                & (SavedMarketArtifact.artifact_ref == event.role_family)
            )
        if not predicates:
            return []
        rows = self._session.execute(
            select(SavedMarketArtifact).where(or_(*predicates)).order_by(
                SavedMarketArtifact.user_id,
                SavedMarketArtifact.created_at,
                SavedMarketArtifact.saved_artifact_id,
            )
        ).scalars()
        return [row for row in rows if _artifact_matches_event(row, event)]

    def list_preference_profiles_for_event(
        self,
        event: AlertEvent,
    ) -> list[UserPreferenceProfile]:
        predicates = []
        if event.region_id:
            predicates.append(UserPreferenceProfile.preferred_regions.contains(event.region_id))
        if event.role_family:
            predicates.append(UserPreferenceProfile.role_interests.contains(event.role_family))
        if not predicates:
            return []
        rows = self._session.execute(
            select(UserPreferenceProfile).where(or_(*predicates)).order_by(
                UserPreferenceProfile.user_id
            )
        ).scalars()
        return [row for row in rows if _preference_matches_event(row, event)]

    def delete_user_alerts_for_user(self, user_id: str) -> int:
        rows = self._session.execute(
            select(UserAlert).where(UserAlert.user_id == user_id)
        ).scalars()
        count = 0
        for row in rows:
            self._session.delete(row)
            count += 1
        return count

    def flush(self) -> None:
        self._session.flush()


def _artifact_matches_event(
    artifact: SavedMarketArtifact,
    event: AlertEvent,
) -> bool:
    if artifact.artifact_type == "company":
        return bool(event.company_id and artifact.artifact_ref == event.company_id)
    if artifact.artifact_type == "region":
        return bool(event.region_id and artifact.artifact_ref == event.region_id)
    if artifact.artifact_type == "role_family":
        return bool(event.role_family and artifact.artifact_ref == event.role_family)
    if artifact.artifact_type == "comparison":
        return bool(
            event.region_id
            and (
                event.region_id in _comparison_region_refs(artifact.artifact_ref)
                or event.region_id in _snapshot_region_refs(artifact.snapshot)
            )
        )
    return False


def _comparison_region_refs(artifact_ref: str) -> set[str]:
    return {part for part in artifact_ref.split("__") if part}


def _snapshot_region_refs(snapshot: object) -> set[str]:
    if not isinstance(snapshot, dict):
        return set()
    region_ids = snapshot.get("region_ids")
    if not isinstance(region_ids, list):
        return set()
    return {item for item in region_ids if isinstance(item, str) and item}


def _preference_matches_event(
    profile: UserPreferenceProfile,
    event: AlertEvent,
) -> bool:
    return bool(
        (event.region_id and event.region_id in (profile.preferred_regions or []))
        or (event.role_family and event.role_family in (profile.role_interests or []))
    )
