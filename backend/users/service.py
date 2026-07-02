"""Map managed-auth identities onto internal app users."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.auth.boundary import ExternalAuthPrincipal
from backend.personalization.controls import (
    ScoringWeightsInput,
    coerce_scoring_weights,
    default_scoring_weights,
)
from backend.users.exceptions import (
    CrossUserAccessBlocked,
    InvalidSavedMarketArtifactType,
    MissingUserForExternalIdentity,
    PreferenceProfileNotFound,
    RecommendationSnapshotNotFound,
    SavedMarketArtifactNotFound,
    UserNotFound,
)
from backend.users.models import (
    ExternalAuthIdentity,
    PersonalizedRecommendationSnapshot,
    SavedMarketArtifact,
    User,
    UserPreferenceProfile,
    UserProfile,
)
from backend.users.repository import UserRepository

PreferenceLevelValue = Literal["low", "medium", "high"]
CareerStageValue = Literal["entry_level"]
RemoteHybridPreferenceValue = Literal["remote", "hybrid", "onsite", "flexible"]
SavedMarketArtifactType = Literal[
    "region",
    "company",
    "role_family",
    "comparison",
    "discovery_result",
]

SAVED_MARKET_ARTIFACT_TYPES: frozenset[str] = frozenset(
    {"region", "company", "role_family", "comparison", "discovery_result"}
)

SNAPSHOT_TOP_LEVEL_KEYS_BY_TYPE: dict[str, frozenset[str]] = {
    "region": frozenset(
        {
            "artifact_type",
            "created_from_route",
            "entity_id",
            "entity_type",
            "label",
            "ref_kind",
            "saved_from",
        }
    ),
    "company": frozenset(
        {
            "artifact_type",
            "created_from_route",
            "entity_id",
            "entity_type",
            "label",
            "ref_kind",
            "saved_from",
        }
    ),
    "role_family": frozenset(
        {
            "artifact_type",
            "created_from_route",
            "entity_id",
            "entity_type",
            "label",
            "ref_kind",
            "role_family",
            "saved_from",
        }
    ),
    "comparison": frozenset(
        {
            "artifact_type",
            "comparison",
            "created_from_route",
            "entity_id",
            "entity_type",
            "label",
            "ref_kind",
            "region_ids",
            "saved_from",
        }
    ),
    "discovery_result": frozenset(
        {
            "artifact_type",
            "created_from_route",
            "entity_id",
            "entity_type",
            "filters",
            "label",
            "objective_output_refs",
            "saved_from",
        }
    ),
}

SAFE_SNAPSHOT_NESTED_KEYS: frozenset[str] = frozenset(
    {
        "artifactref",
        "artifacttype",
        "brandpreference",
        "careerstage",
        "companyid",
        "comparison",
        "createdfromroute",
        "entityid",
        "entitytype",
        "filters",
        "id",
        "industries",
        "industrypreferences",
        "key",
        "label",
        "limit",
        "name",
        "objectiveoutputrefs",
        "outputtype",
        "prestigepreference",
        "refkind",
        "regionid",
        "regionids",
        "rolefamily",
        "roletargets",
        "savedfrom",
        "selectedregions",
        "subjectid",
        "value",
    }
)

UNSAFE_SNAPSHOT_KEY_NAMES: frozenset[str] = frozenset(
    {
        "canonicalscore",
        "companies",
        "companydetail",
        "entrylevelsignal",
        "evidence",
        "freshness",
        "hiring",
        "marketoutput",
        "output",
        "personalizedscore",
        "provenance",
        "regiondetail",
        "regions",
        "score",
        "scores",
        "sources",
        "sourcesummary",
    }
)
UNSAFE_SNAPSHOT_KEY_PARTS: tuple[str, ...] = (
    "score",
    "freshness",
    "provenance",
    "source",
    "evidence",
    "hiring",
    "entrylevel",
    "marketoutput",
    "companydetail",
    "regiondetail",
)


@dataclass(frozen=True, slots=True)
class UserIdentityResolution:
    user: User
    identity: ExternalAuthIdentity
    profile: UserProfile
    created_user: bool
    created_identity: bool


@dataclass(frozen=True, slots=True)
class UserPrivacyDeletionResult:
    user_id: str
    user_status: str
    deleted_preference_profiles: int
    deleted_saved_market_artifacts: int
    deleted_recommendation_snapshots: int
    deleted_user_alerts: int
    deleted_profiles: int
    deleted_external_auth_identities: int


class UserIdentityService:
    """Resolve current-user identity after external auth verification."""

    def __init__(self, repository: UserRepository) -> None:
        self._repo = repository

    def resolve_external_principal(
        self, principal: ExternalAuthPrincipal
    ) -> UserIdentityResolution:
        provider, issuer, subject = principal.identity_key
        identity = self._repo.get_external_identity(
            provider=provider,
            issuer=issuer,
            subject=subject,
        )
        if identity is not None:
            user = self._repo.get_user(identity.user_id)
            if user is None:
                raise MissingUserForExternalIdentity(identity.user_id)
            identity.email = principal.email
            identity.email_verified = principal.email_verified
            identity.last_seen_at = datetime.now(UTC)
            profile = self._get_or_create_profile(user, principal)
            self._sync_profile(profile, principal)
            self._repo.flush()
            return UserIdentityResolution(
                user=user,
                identity=identity,
                profile=profile,
                created_user=False,
                created_identity=False,
            )

        user = User(user_id=_new_user_id())
        identity = ExternalAuthIdentity(
            external_identity_id=_new_external_identity_id(),
            user_id=user.user_id,
            provider=provider,
            issuer=issuer,
            subject=subject,
            email=principal.email,
            email_verified=principal.email_verified,
            last_seen_at=datetime.now(UTC),
        )
        profile = UserProfile(user_id=user.user_id)
        self._sync_profile(profile, principal)

        self._repo.add_user(user)
        self._repo.flush()
        self._repo.add_external_identity(identity)
        self._repo.add_profile(profile)
        self._repo.flush()
        return UserIdentityResolution(
            user=user,
            identity=identity,
            profile=profile,
            created_user=True,
            created_identity=True,
        )

    def _get_or_create_profile(
        self,
        user: User,
        principal: ExternalAuthPrincipal,
    ) -> UserProfile:
        profile = self._repo.get_profile(user.user_id)
        if profile is not None:
            return profile
        profile = UserProfile(user_id=user.user_id)
        self._sync_profile(profile, principal)
        self._repo.add_profile(profile)
        return profile

    def _sync_profile(
        self,
        profile: UserProfile,
        principal: ExternalAuthPrincipal,
    ) -> None:
        if principal.display_name is not None:
            profile.display_name = principal.display_name
        if principal.email is not None:
            profile.email = principal.email
        if principal.avatar_url is not None:
            profile.avatar_url = principal.avatar_url


def _new_user_id() -> str:
    return f"user_{uuid4().hex}"


def _new_external_identity_id() -> str:
    return f"external_identity_{uuid4().hex[:46]}"


class UserPreferenceProfileInput(BaseModel):
    """User-owned saved preference inputs.

    Empty lists and ``None`` weighting fields represent neutral/default
    preferences. They are not interpreted as objective market facts.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    role_interests: list[str] = Field(default_factory=list)
    industry_interests: list[str] = Field(default_factory=list)
    preferred_regions: list[str] = Field(default_factory=list)
    prestige_weighting: PreferenceLevelValue | None = None
    brand_weighting: PreferenceLevelValue | None = None
    career_stage: CareerStageValue | None = None
    remote_hybrid_preference: RemoteHybridPreferenceValue | None = None
    scoring_weights: ScoringWeightsInput | None = None

    @field_validator("role_interests", "industry_interests", "preferred_regions")
    @classmethod
    def _strings_must_be_non_empty(cls, value: list[str]) -> list[str]:
        cleaned: list[str] = []
        for item in value:
            if not isinstance(item, str) or not item.strip():
                raise ValueError("entries must be non-empty strings")
            cleaned.append(item.strip())
        return cleaned


class UserPreferenceProfileView(UserPreferenceProfileInput):
    user_id: str
    persisted: bool
    scoring_weights: ScoringWeightsInput


class SavedMarketArtifactInput(BaseModel):
    """User-owned saved market reference plus narrow reference metadata.

    ``snapshot`` may carry only user-owned references/configuration. It must
    not persist copied canonical company/region facts, scores, freshness,
    provenance, source summaries, or assembled market outputs.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    artifact_type: SavedMarketArtifactType
    artifact_ref: str = Field(min_length=1, max_length=255)
    label: str | None = Field(default=None, max_length=255)
    notes: str | None = Field(default=None, max_length=2048)
    snapshot: dict[str, Any] | None = None

    @field_validator("artifact_ref", "label", "notes")
    @classmethod
    def _strip_optional_strings(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("string fields must not be blank when provided")
        return stripped

    @model_validator(mode="after")
    def _snapshot_must_be_reference_only(self) -> SavedMarketArtifactInput:
        if self.snapshot is None:
            return self
        _validate_saved_artifact_snapshot(
            artifact_type=self.artifact_type,
            snapshot=self.snapshot,
        )
        return self


class PersonalizedRecommendationSnapshotInput(BaseModel):
    """Derived personalized output owned by one internal user."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    preference_profile_id: str | None = Field(default=None, max_length=64)
    personalized_output: dict[str, Any] | list[Any]
    recommendation_version: str = Field(min_length=1, max_length=64)
    source_version_bundle: dict[str, Any] | list[Any]
    objective_output_refs: list[dict[str, Any] | str] = Field(default_factory=list)
    recommendation_inputs_hash: str = Field(min_length=1, max_length=128)
    generated_at: datetime

    @field_validator(
        "preference_profile_id",
        "recommendation_version",
        "recommendation_inputs_hash",
    )
    @classmethod
    def _strip_snapshot_strings(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("string fields must not be blank when provided")
        return stripped

    @field_validator("objective_output_refs")
    @classmethod
    def _objective_refs_must_be_non_empty(
        cls,
        value: list[dict[str, Any] | str],
    ) -> list[dict[str, Any] | str]:
        cleaned: list[dict[str, Any] | str] = []
        for item in value:
            if isinstance(item, str):
                stripped = item.strip()
                if not stripped:
                    raise ValueError("objective output refs must not be blank")
                cleaned.append(stripped)
            else:
                cleaned.append(item)
        return cleaned

    @field_validator("generated_at")
    @classmethod
    def _generated_at_must_be_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("generated_at must be timezone-aware")
        return value


class UserPersonalizationPersistenceService:
    """Persist and manage user-owned Layer 7 data.

    The service is deliberately scoped by current internal ``user_id``. It does
    not perform provider token validation and does not read or mutate objective
    market truth.
    """

    def __init__(self, repository: UserRepository) -> None:
        self._repo = repository

    def get_preference_profile(
        self,
        current_user_id: str,
        *,
        owner_user_id: str | None = None,
    ) -> UserPreferenceProfileView:
        owner_user_id = self._owner_or_current(current_user_id, owner_user_id)
        self._ensure_user(current_user_id)
        row = self._repo.get_preference_profile(owner_user_id)
        if row is None:
            return UserPreferenceProfileView(
                user_id=owner_user_id,
                persisted=False,
                scoring_weights=default_scoring_weights(),
            )
        return _preference_view(row, persisted=True)

    def upsert_preference_profile(
        self,
        current_user_id: str,
        profile: UserPreferenceProfileInput,
        *,
        owner_user_id: str | None = None,
    ) -> UserPreferenceProfileView:
        owner_user_id = self._owner_or_current(current_user_id, owner_user_id)
        self._ensure_user(current_user_id)
        row = self._repo.get_preference_profile(owner_user_id)
        if row is None:
            row = UserPreferenceProfile(user_id=owner_user_id)
            self._repo.add_preference_profile(row)
        _apply_preference_input(row, profile)
        self._repo.flush()
        return _preference_view(row, persisted=True)

    def save_market_artifact(
        self,
        current_user_id: str,
        artifact: SavedMarketArtifactInput,
    ) -> SavedMarketArtifact:
        self._ensure_user(current_user_id)
        row = SavedMarketArtifact(
            saved_artifact_id=_new_saved_artifact_id(),
            user_id=current_user_id,
            artifact_type=artifact.artifact_type,
            artifact_ref=artifact.artifact_ref,
            label=artifact.label,
            notes=artifact.notes,
            snapshot=artifact.snapshot,
        )
        self._repo.add_saved_market_artifact(row)
        self._repo.flush()
        return row

    def list_saved_market_artifacts(
        self,
        current_user_id: str,
        *,
        artifact_type: str | None = None,
    ) -> list[SavedMarketArtifact]:
        self._ensure_user(current_user_id)
        if artifact_type is not None and artifact_type not in SAVED_MARKET_ARTIFACT_TYPES:
            raise InvalidSavedMarketArtifactType(artifact_type)
        return self._repo.list_saved_market_artifacts(
            user_id=current_user_id,
            artifact_type=artifact_type,
        )

    def get_saved_market_artifact(
        self,
        current_user_id: str,
        saved_artifact_id: str,
    ) -> SavedMarketArtifact:
        self._ensure_user(current_user_id)
        row = self._repo.get_saved_market_artifact(saved_artifact_id)
        if row is None:
            raise SavedMarketArtifactNotFound(saved_artifact_id)
        if row.user_id != current_user_id:
            raise CrossUserAccessBlocked(current_user_id, row.user_id)
        return row

    def delete_saved_market_artifact(
        self,
        current_user_id: str,
        saved_artifact_id: str,
    ) -> None:
        row = self.get_saved_market_artifact(current_user_id, saved_artifact_id)
        self._repo.delete_saved_market_artifact(row)
        self._repo.flush()

    def create_recommendation_snapshot(
        self,
        current_user_id: str,
        snapshot: PersonalizedRecommendationSnapshotInput,
    ) -> PersonalizedRecommendationSnapshot:
        self._ensure_user(current_user_id)
        if snapshot.preference_profile_id is not None:
            if snapshot.preference_profile_id != current_user_id:
                raise CrossUserAccessBlocked(
                    current_user_id,
                    snapshot.preference_profile_id,
                )
            if self._repo.get_preference_profile(snapshot.preference_profile_id) is None:
                raise PreferenceProfileNotFound(snapshot.preference_profile_id)

        row = PersonalizedRecommendationSnapshot(
            recommendation_snapshot_id=_new_recommendation_snapshot_id(),
            user_id=current_user_id,
            preference_profile_id=snapshot.preference_profile_id,
            personalized_output=deepcopy(snapshot.personalized_output),
            recommendation_version=snapshot.recommendation_version,
            source_version_bundle=deepcopy(snapshot.source_version_bundle),
            objective_output_refs=deepcopy(snapshot.objective_output_refs),
            recommendation_inputs_hash=snapshot.recommendation_inputs_hash,
            generated_at=snapshot.generated_at,
        )
        self._repo.add_recommendation_snapshot(row)
        self._repo.flush()
        return row

    def list_recommendation_snapshots(
        self,
        current_user_id: str,
        *,
        owner_user_id: str | None = None,
    ) -> list[PersonalizedRecommendationSnapshot]:
        owner_user_id = self._owner_or_current(current_user_id, owner_user_id)
        self._ensure_user(current_user_id)
        return self._repo.list_recommendation_snapshots(user_id=owner_user_id)

    def get_recommendation_snapshot(
        self,
        current_user_id: str,
        recommendation_snapshot_id: str,
    ) -> PersonalizedRecommendationSnapshot:
        self._ensure_user(current_user_id)
        row = self._repo.get_recommendation_snapshot(recommendation_snapshot_id)
        if row is None:
            raise RecommendationSnapshotNotFound(recommendation_snapshot_id)
        if row.user_id != current_user_id:
            raise CrossUserAccessBlocked(current_user_id, row.user_id)
        return row

    def export_user_data(
        self,
        current_user_id: str,
        *,
        owner_user_id: str | None = None,
    ) -> dict[str, Any]:
        owner_user_id = self._owner_or_current(current_user_id, owner_user_id)
        user = self._ensure_user(current_user_id)
        profile = self._repo.get_profile(owner_user_id)
        preference = self._repo.get_preference_profile(owner_user_id)
        return {
            "export_schema_version": "layer7_privacy_export_v1",
            "user": _export_user(user),
            "profile": _export_profile(profile) if profile is not None else None,
            "external_auth_identities": [
                _export_external_identity(identity)
                for identity in self._repo.list_external_identities(owner_user_id)
            ],
            "preference_profile": (
                _export_preference_profile(preference)
                if preference is not None
                else None
            ),
            "saved_market_artifacts": [
                _export_saved_market_artifact(artifact)
                for artifact in self._repo.list_saved_market_artifacts(
                    user_id=owner_user_id
                )
            ],
            "personalized_recommendation_snapshots": [
                _export_recommendation_snapshot(snapshot)
                for snapshot in self._repo.list_recommendation_snapshots(
                    user_id=owner_user_id
                )
            ],
            "user_alerts": [
                _export_user_alert(alert)
                for alert in self._repo.list_user_alerts_for_user(owner_user_id)
            ],
        }

    def delete_preference_profile(
        self,
        current_user_id: str,
        *,
        owner_user_id: str | None = None,
    ) -> int:
        owner_user_id = self._owner_or_current(current_user_id, owner_user_id)
        self._ensure_user(current_user_id)
        row = self._repo.get_preference_profile(owner_user_id)
        if row is None:
            return 0
        self._repo.clear_snapshot_preference_profile_for_user(owner_user_id)
        self._repo.flush()
        self._repo.delete_preference_profile(row)
        self._repo.flush()
        return 1

    def delete_saved_market_artifacts(
        self,
        current_user_id: str,
        *,
        owner_user_id: str | None = None,
    ) -> int:
        owner_user_id = self._owner_or_current(current_user_id, owner_user_id)
        self._ensure_user(current_user_id)
        count = self._repo.delete_saved_market_artifacts_for_user(owner_user_id)
        self._repo.flush()
        return count

    def delete_recommendation_snapshots(
        self,
        current_user_id: str,
        *,
        owner_user_id: str | None = None,
    ) -> int:
        owner_user_id = self._owner_or_current(current_user_id, owner_user_id)
        self._ensure_user(current_user_id)
        count = self._repo.delete_recommendation_snapshots_for_user(owner_user_id)
        self._repo.flush()
        return count

    def deactivate_user_account(
        self,
        current_user_id: str,
        *,
        owner_user_id: str | None = None,
    ) -> UserPrivacyDeletionResult:
        owner_user_id = self._owner_or_current(current_user_id, owner_user_id)
        user = self._ensure_user(current_user_id)
        deleted_snapshots = self._repo.delete_recommendation_snapshots_for_user(
            owner_user_id
        )
        deleted_user_alerts = self._repo.delete_user_alerts_for_user(owner_user_id)
        self._repo.delete_career_memory_for_user(owner_user_id)
        self._repo.delete_career_agent_tool_records_for_user(owner_user_id)
        deleted_artifacts = self._repo.delete_saved_market_artifacts_for_user(
            owner_user_id
        )
        preference = self._repo.get_preference_profile(owner_user_id)
        deleted_preferences = 0
        if preference is not None:
            self._repo.delete_preference_profile(preference)
            deleted_preferences = 1
        profile = self._repo.get_profile(owner_user_id)
        deleted_profiles = 0
        if profile is not None:
            self._repo.delete_profile(profile)
            deleted_profiles = 1
        deleted_identities = self._repo.delete_external_identities_for_user(
            owner_user_id
        )
        user.status = "deactivated"
        self._repo.flush()
        return UserPrivacyDeletionResult(
            user_id=owner_user_id,
            user_status=user.status,
            deleted_preference_profiles=deleted_preferences,
            deleted_saved_market_artifacts=deleted_artifacts,
            deleted_recommendation_snapshots=deleted_snapshots,
            deleted_user_alerts=deleted_user_alerts,
            deleted_profiles=deleted_profiles,
            deleted_external_auth_identities=deleted_identities,
        )

    def _owner_or_current(
        self,
        current_user_id: str,
        owner_user_id: str | None,
    ) -> str:
        owner = owner_user_id or current_user_id
        if owner != current_user_id:
            raise CrossUserAccessBlocked(current_user_id, owner)
        return owner

    def _ensure_user(self, user_id: str) -> User:
        user = self._repo.get_user(user_id)
        if user is None:
            raise UserNotFound(user_id)
        return user


def _validate_saved_artifact_snapshot(
    *,
    artifact_type: str,
    snapshot: dict[str, Any],
) -> None:
    allowed_top_level = SNAPSHOT_TOP_LEVEL_KEYS_BY_TYPE.get(artifact_type)
    if allowed_top_level is None:
        raise ValueError(f"invalid saved artifact type: {artifact_type!r}")

    for key, value in snapshot.items():
        if key not in allowed_top_level:
            raise ValueError(
                f"saved artifact snapshot field {key!r} is not allowed for "
                f"{artifact_type!r} artifacts"
            )
        _validate_snapshot_value(key, value, path=f"snapshot.{key}")


def _validate_snapshot_value(key: str, value: Any, *, path: str) -> None:
    _validate_snapshot_key(key, path=path)
    if value is None or isinstance(value, str | int | float | bool):
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_snapshot_value("value", item, path=f"{path}[{index}]")
        return
    if isinstance(value, dict):
        for nested_key, nested_value in value.items():
            if not isinstance(nested_key, str) or not nested_key.strip():
                raise ValueError("saved artifact snapshot object keys must be non-empty strings")
            _validate_snapshot_value(
                nested_key,
                nested_value,
                path=f"{path}.{nested_key}",
            )
        return
    raise ValueError(
        f"saved artifact snapshot field {path!r} must contain only JSON primitives, "
        "lists, or objects"
    )


def _validate_snapshot_key(key: str, *, path: str) -> None:
    normalized = _normalize_snapshot_key(key)
    if normalized in SAFE_SNAPSHOT_NESTED_KEYS:
        return
    if normalized in UNSAFE_SNAPSHOT_KEY_NAMES or any(
        part in normalized for part in UNSAFE_SNAPSHOT_KEY_PARTS
    ):
        raise ValueError(
            f"saved artifact snapshot field {path!r} may only contain user-owned "
            "references/configuration, not copied market facts"
        )


def _normalize_snapshot_key(key: str) -> str:
    return "".join(character for character in key.casefold() if character.isalnum())


def _apply_preference_input(
    row: UserPreferenceProfile,
    profile: UserPreferenceProfileInput,
) -> None:
    row.role_interests = list(profile.role_interests)
    row.industry_interests = list(profile.industry_interests)
    row.preferred_regions = list(profile.preferred_regions)
    row.prestige_weighting = profile.prestige_weighting
    row.brand_weighting = profile.brand_weighting
    row.career_stage = profile.career_stage
    row.remote_hybrid_preference = profile.remote_hybrid_preference
    row.scoring_weights = (
        profile.scoring_weights.model_dump(mode="json")
        if profile.scoring_weights is not None
        else None
    )


def _stored_scoring_weights_or_default(value: object | None) -> ScoringWeightsInput:
    try:
        return coerce_scoring_weights(value)
    except (TypeError, ValueError):
        return default_scoring_weights()


def _preference_view(
    row: UserPreferenceProfile,
    *,
    persisted: bool,
) -> UserPreferenceProfileView:
    return UserPreferenceProfileView(
        user_id=row.user_id,
        persisted=persisted,
        role_interests=list(row.role_interests or []),
        industry_interests=list(row.industry_interests or []),
        preferred_regions=list(row.preferred_regions or []),
        prestige_weighting=row.prestige_weighting,
        brand_weighting=row.brand_weighting,
        career_stage=row.career_stage,
        remote_hybrid_preference=row.remote_hybrid_preference,
        scoring_weights=_stored_scoring_weights_or_default(row.scoring_weights),
    )


def _export_datetime(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _export_user(row: User) -> dict[str, Any]:
    return {
        "user_id": row.user_id,
        "status": row.status,
        "created_at": _export_datetime(row.created_at),
        "updated_at": _export_datetime(row.updated_at),
    }


def _export_external_identity(row: ExternalAuthIdentity) -> dict[str, Any]:
    return {
        "external_identity_id": row.external_identity_id,
        "provider": row.provider,
        "issuer": row.issuer,
        "subject": row.subject,
        "email": row.email,
        "email_verified": row.email_verified,
        "last_seen_at": _export_datetime(row.last_seen_at),
        "created_at": _export_datetime(row.created_at),
        "updated_at": _export_datetime(row.updated_at),
    }


def _export_profile(row: UserProfile) -> dict[str, Any]:
    return {
        "user_id": row.user_id,
        "display_name": row.display_name,
        "email": row.email,
        "avatar_url": row.avatar_url,
        "created_at": _export_datetime(row.created_at),
        "updated_at": _export_datetime(row.updated_at),
    }


def _export_preference_profile(row: UserPreferenceProfile) -> dict[str, Any]:
    return {
        "user_id": row.user_id,
        "role_interests": list(row.role_interests or []),
        "industry_interests": list(row.industry_interests or []),
        "preferred_regions": list(row.preferred_regions or []),
        "prestige_weighting": row.prestige_weighting,
        "brand_weighting": row.brand_weighting,
        "career_stage": row.career_stage,
        "remote_hybrid_preference": row.remote_hybrid_preference,
        "scoring_weights": _stored_scoring_weights_or_default(
            row.scoring_weights
        ).model_dump(mode="json"),
        "created_at": _export_datetime(row.created_at),
        "updated_at": _export_datetime(row.updated_at),
    }


def _export_saved_market_artifact(row: SavedMarketArtifact) -> dict[str, Any]:
    return {
        "saved_artifact_id": row.saved_artifact_id,
        "user_id": row.user_id,
        "artifact_type": row.artifact_type,
        "artifact_ref": row.artifact_ref,
        "label": row.label,
        "notes": row.notes,
        "snapshot": deepcopy(row.snapshot),
        "created_at": _export_datetime(row.created_at),
        "updated_at": _export_datetime(row.updated_at),
    }


def _export_recommendation_snapshot(
    row: PersonalizedRecommendationSnapshot,
) -> dict[str, Any]:
    return {
        "recommendation_snapshot_id": row.recommendation_snapshot_id,
        "user_id": row.user_id,
        "preference_profile_id": row.preference_profile_id,
        "personalized_output": deepcopy(row.personalized_output),
        "recommendation_version": row.recommendation_version,
        "source_version_bundle": deepcopy(row.source_version_bundle),
        "objective_output_refs": deepcopy(row.objective_output_refs),
        "recommendation_inputs_hash": row.recommendation_inputs_hash,
        "generated_at": _export_datetime(row.generated_at),
        "created_at": _export_datetime(row.created_at),
        "updated_at": _export_datetime(row.updated_at),
    }


def _export_user_alert(row: Any) -> dict[str, Any]:
    return {
        "user_alert_id": row.user_alert_id,
        "user_id": row.user_id,
        "alert_event_id": row.alert_event_id,
        "relevance_reason": row.relevance_reason,
        "relevance_artifact_id": row.relevance_artifact_id,
        "relevance_artifact_type": row.relevance_artifact_type,
        "relevance_artifact_ref": row.relevance_artifact_ref,
        "is_read": row.is_read,
        "dismissed": row.dismissed,
        "created_at": _export_datetime(row.created_at),
        "updated_at": _export_datetime(row.updated_at),
        "read_at": _export_datetime(row.read_at),
        "dismissed_at": _export_datetime(row.dismissed_at),
    }


def _new_saved_artifact_id() -> str:
    return f"saved_artifact_{uuid4().hex[:47]}"


def _new_recommendation_snapshot_id() -> str:
    return f"recommendation_snapshot_{uuid4().hex[:40]}"
