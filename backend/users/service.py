"""Map managed-auth identities onto internal app users."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.auth.boundary import ExternalAuthPrincipal
from backend.geography.repository import RegionRepository
from backend.geography.resolver import GeographicResolution, GeographicResolver
from backend.personalization.controls import (
    ScoringWeightsInput,
    coerce_scoring_weights,
    default_scoring_weights,
)
from backend.shared.redaction import redact_sensitive
from backend.users.exceptions import (
    CrossUserAccessBlocked,
    DeactivatedUserAuthenticationBlocked,
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
    deleted_career_identities: int
    deleted_career_identity_facts: int
    deleted_career_identity_imports: int
    deleted_preference_profiles: int
    deleted_saved_market_artifacts: int
    deleted_recommendation_snapshots: int
    deleted_user_alerts: int
    deleted_career_decision_records: int
    deleted_deep_decision_records: int
    deleted_profiles: int
    deleted_external_auth_identities: int
    scrubbed_external_auth_identities: int


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
            if user.status != "active":
                raise DeactivatedUserAuthenticationBlocked(user.user_id)
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

    def __init__(
        self,
        repository: UserRepository,
        region_repository: RegionRepository | None = None,
    ) -> None:
        self._repo = repository
        self._geographic_resolver = GeographicResolver(
            region_repository or RegionRepository(repository.session)
        )

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
        canonical_preferred_regions: list[str] = []
        for value in profile.preferred_regions:
            resolution = self._geographic_resolver.require(value)
            assert resolution.region_id is not None
            canonical_preferred_regions.append(resolution.region_id)
        profile = profile.model_copy(
            update={"preferred_regions": list(dict.fromkeys(canonical_preferred_regions))}
        )
        row = self._repo.get_preference_profile(owner_user_id)
        if row is None:
            row = UserPreferenceProfile(user_id=owner_user_id)
            self._repo.add_preference_profile(row)
        _apply_preference_input(
            row,
            profile,
            geographic_resolver=self._geographic_resolver,
        )
        self._repo.flush()
        return _preference_view(row, persisted=True)

    def save_market_artifact(
        self,
        current_user_id: str,
        artifact: SavedMarketArtifactInput,
    ) -> SavedMarketArtifact:
        self._ensure_user(current_user_id)
        artifact_ref = artifact.artifact_ref
        if artifact.artifact_type == "region":
            resolution = self._geographic_resolver.require(artifact_ref)
            assert resolution.region_id is not None
            artifact_ref = resolution.region_id
        row = SavedMarketArtifact(
            saved_artifact_id=_new_saved_artifact_id(),
            user_id=current_user_id,
            artifact_type=artifact.artifact_type,
            artifact_ref=artifact_ref,
            label=artifact.label,
            notes=artifact.notes,
            snapshot=artifact.snapshot,
        )
        self._repo.add_saved_market_artifact(row)
        self._repo.flush()
        return row

    def resolve_saved_region_reference(
        self, row: SavedMarketArtifact
    ) -> GeographicResolution | None:
        """Interpret a legacy region save without rewriting its historical row."""

        if row.artifact_type != "region":
            return None
        return self._geographic_resolver.resolve(row.artifact_ref)

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
                _export_preference_profile(preference) if preference is not None else None
            ),
            "saved_market_artifacts": [
                _export_saved_market_artifact(artifact)
                for artifact in self._repo.list_saved_market_artifacts(user_id=owner_user_id)
            ],
            "personalized_recommendation_snapshots": [
                _export_recommendation_snapshot(snapshot)
                for snapshot in self._repo.list_recommendation_snapshots(user_id=owner_user_id)
            ],
            "career_identity": _export_career_identity(
                self._repo.get_career_identity_for_user(owner_user_id),
                self._repo.list_career_identity_facts_for_user(owner_user_id),
                self._repo.list_career_identity_imports_for_user(owner_user_id),
            ),
            "user_alerts": [
                _export_user_alert(alert)
                for alert in self._repo.list_user_alerts_for_user(owner_user_id)
            ],
            "career_agent_memory": _export_career_agent_memory(
                self._repo.list_career_memory_permissions_for_user(owner_user_id),
                self._repo.list_career_memory_entries_for_user(owner_user_id),
            ),
            "career_agent_tools": _export_career_agent_tools(
                self._repo.list_career_agent_tool_records_for_user(owner_user_id),
                self._repo.list_career_agent_tool_audit_events_for_user(owner_user_id),
            ),
            "career_decisions": _export_career_decision_bundle(
                self._repo.list_career_decisions_for_user(owner_user_id),
                self._repo.list_decision_context_snapshots_for_user(owner_user_id),
                self._repo.list_decision_options_for_user(owner_user_id),
                self._repo.list_decision_recommendations_for_user(owner_user_id),
                self._repo.list_decision_versions_for_user(owner_user_id),
                self._repo.list_career_action_plans_for_user(owner_user_id),
                self._repo.list_career_actions_for_user(owner_user_id),
                self._repo.list_career_applications_for_user(owner_user_id),
                self._repo.list_career_application_transitions_for_user(owner_user_id),
                self._repo.list_career_outcomes_for_user(owner_user_id),
            ),
            "deep_decision_intelligence": _export_deep_decision_bundle(
                self._repo.list_decision_factors_for_user(owner_user_id),
                self._repo.list_longitudinal_context_snapshots_for_user(owner_user_id),
                self._repo.list_recommendation_evolutions_for_user(owner_user_id),
                self._repo.list_advisory_findings_for_user(owner_user_id),
                self._repo.list_strategic_career_reviews_for_user(owner_user_id),
            ),
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
        deleted_snapshots = self._repo.delete_recommendation_snapshots_for_user(owner_user_id)
        deleted_user_alerts = self._repo.delete_user_alerts_for_user(owner_user_id)
        self._repo.delete_career_memory_for_user(owner_user_id)
        self._repo.delete_career_agent_tool_records_for_user(owner_user_id)
        deleted_deep_decisions = self._repo.delete_deep_decision_data_for_user(owner_user_id)
        deleted_career_decisions = self._repo.delete_career_decision_data_for_user(owner_user_id)
        (
            deleted_career_identities,
            deleted_career_identity_facts,
            deleted_career_identity_imports,
        ) = self._repo.delete_career_identity_for_user(owner_user_id)
        deleted_artifacts = self._repo.delete_saved_market_artifacts_for_user(owner_user_id)
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
        scrubbed_identities = self._repo.scrub_external_identities_for_deactivated_user(
            owner_user_id
        )
        user.status = "deactivated"
        self._repo.flush()
        return UserPrivacyDeletionResult(
            user_id=owner_user_id,
            user_status=user.status,
            deleted_career_identities=deleted_career_identities,
            deleted_career_identity_facts=deleted_career_identity_facts,
            deleted_career_identity_imports=deleted_career_identity_imports,
            deleted_preference_profiles=deleted_preferences,
            deleted_saved_market_artifacts=deleted_artifacts,
            deleted_recommendation_snapshots=deleted_snapshots,
            deleted_user_alerts=deleted_user_alerts,
            deleted_career_decision_records=deleted_career_decisions,
            deleted_deep_decision_records=deleted_deep_decisions,
            deleted_profiles=deleted_profiles,
            deleted_external_auth_identities=0,
            scrubbed_external_auth_identities=scrubbed_identities,
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
    *,
    geographic_resolver: GeographicResolver,
) -> None:
    row.role_interests = list(profile.role_interests)
    row.industry_interests = list(profile.industry_interests)
    preferred_regions: list[str] = []
    for value in profile.preferred_regions:
        resolution = geographic_resolver.require(value)
        assert resolution.region_id is not None
        preferred_regions.append(resolution.region_id)
    row.preferred_regions = list(dict.fromkeys(preferred_regions))
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
        "scoring_weights": _stored_scoring_weights_or_default(row.scoring_weights).model_dump(
            mode="json"
        ),
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


def _export_career_identity(
    identity: Any | None,
    facts: list[Any],
    imports: list[Any],
) -> dict[str, Any] | None:
    if identity is None:
        return None
    return {
        "career_identity_id": identity.career_identity_id,
        "user_id": identity.user_id,
        "current_version": identity.current_version,
        "completeness_state": identity.completeness_state,
        "sufficiency_state": identity.sufficiency_state,
        "privacy": {
            "privacy_visibility": identity.privacy_visibility,
            "ingestion_consent_granted": identity.ingestion_consent_granted,
            "inference_consent_granted": identity.inference_consent_granted,
            "downstream_personalization_consent_granted": (
                identity.downstream_personalization_consent_granted
            ),
            "retain_import_metadata": identity.retain_import_metadata,
            "raw_import_content_exposed": False,
        },
        "completeness": deepcopy(identity.completeness_snapshot),
        "facts": [
            {
                "career_identity_fact_id": fact.career_identity_fact_id,
                "fact_type": fact.fact_type,
                "normalized_key": fact.normalized_key,
                "state": fact.state,
                "payload": deepcopy(fact.payload),
                "provenance": deepcopy(fact.provenance),
                "source_import_id": fact.source_import_id,
                "source_label": fact.source_label,
                "confirmed_at": _export_datetime(fact.confirmed_at),
                "created_at": _export_datetime(fact.created_at),
                "updated_at": _export_datetime(fact.updated_at),
            }
            for fact in facts
        ],
        "imports": [
            {
                "career_identity_import_id": row.career_identity_import_id,
                "source_type": row.source_type,
                "source_label": row.source_label,
                "content_hash": row.content_hash,
                "artifact_metadata": deepcopy(row.artifact_metadata),
                "import_status": row.import_status,
                "diagnostics": deepcopy(row.diagnostics),
                "imported_fact_count": row.imported_fact_count,
                "created_at": _export_datetime(row.created_at),
                "updated_at": _export_datetime(row.updated_at),
            }
            for row in imports
        ],
        "raw_import_content_retained": False,
        "created_at": _export_datetime(identity.created_at),
        "updated_at": _export_datetime(identity.updated_at),
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


def _export_career_agent_memory(
    permissions: list[Any],
    entries: list[Any],
) -> dict[str, Any]:
    return {
        "permissions": [
            {
                "category": row.category,
                "enabled": row.enabled,
                "personalize_allowed": row.personalize_allowed,
                "visibility": row.visibility,
                "created_at": _export_datetime(row.created_at),
                "updated_at": _export_datetime(row.updated_at),
            }
            for row in permissions
        ],
        "entries": [
            {
                "memory_entry_id": row.career_memory_entry_id,
                "category": row.category,
                "value": redact_sensitive(row.value),
                "label": redact_sensitive(row.label),
                "notes": redact_sensitive(row.notes),
                "visibility": row.visibility,
                "source": row.source,
                "counts_as_evidence": False,
                "created_at": _export_datetime(row.created_at),
                "updated_at": _export_datetime(row.updated_at),
            }
            for row in entries
        ],
    }


def _export_career_agent_tools(
    tool_rows: list[Any],
    audit_rows: list[Any],
) -> list[dict[str, Any]]:
    audit_by_tool: dict[str, list[Any]] = {}
    for row in audit_rows:
        audit_by_tool.setdefault(row.career_agent_tool_id, []).append(row)
    return [
        {
            "tool_request_id": row.career_agent_tool_id,
            "tool_type": row.tool_type,
            "status": row.status,
            "action_boundary": row.action_boundary,
            "privacy_classification": row.privacy_classification,
            "approval_required": row.approval_required,
            "explicit_user_approval_required": row.explicit_user_approval_required,
            "approval_reason": redact_sensitive(row.approval_reason),
            "proposed_action_summary": redact_sensitive(row.proposed_action_summary),
            "user_visible_preview": redact_sensitive(deepcopy(row.preview_payload)),
            "evidence_refs": redact_sensitive(deepcopy(row.evidence_refs)),
            "freshness": redact_sensitive(deepcopy(row.freshness)),
            "uncertainty": redact_sensitive(deepcopy(row.uncertainty)),
            "warnings": redact_sensitive(deepcopy(row.warnings)),
            "source_answer_id": row.source_answer_id,
            "source_plan_id": row.source_plan_id,
            "runtime_execution_performed": row.runtime_execution_performed,
            "approved_at": _export_datetime(row.approved_at),
            "rejected_at": _export_datetime(row.rejected_at),
            "executed_at": _export_datetime(row.executed_at),
            "created_at": _export_datetime(row.created_at),
            "updated_at": _export_datetime(row.updated_at),
            "audit_events": [
                {
                    "event_type": audit.event_type,
                    "summary": redact_sensitive(audit.summary),
                    "occurred_at": _export_datetime(audit.created_at),
                }
                for audit in audit_by_tool.get(row.career_agent_tool_id, [])
            ],
        }
        for row in tool_rows
    ]


def _export_career_decision_bundle(
    decisions: list[Any],
    contexts: list[Any],
    options: list[Any],
    recommendations: list[Any],
    versions: list[Any],
    plans: list[Any],
    actions: list[Any],
    applications: list[Any],
    transitions: list[Any],
    outcomes: list[Any],
) -> dict[str, Any]:
    return {
        "decisions": [
            {
                "decision_id": row.decision_id,
                "user_id": row.user_id,
                "career_identity_id": row.career_identity_id,
                "current_context_snapshot_id": row.current_context_snapshot_id,
                "current_recommendation_id": row.current_recommendation_id,
                "selected_option_id": row.selected_option_id,
                "decision_type": row.decision_type,
                "status": row.status,
                "title": row.title,
                "description": row.description,
                "decision_date": _export_datetime(row.decision_date),
                "target_date": _export_datetime(row.target_date),
                "planned_review_at": _export_datetime(row.planned_review_at),
                "time_horizon": row.time_horizon,
                "priorities": deepcopy(row.priorities),
                "constraints": deepcopy(row.constraints),
                "current_version": row.current_version,
                "created_at": _export_datetime(row.created_at),
                "updated_at": _export_datetime(row.updated_at),
            }
            for row in decisions
        ],
        "context_snapshots": [
            {
                "context_snapshot_id": row.context_snapshot_id,
                "user_id": row.user_id,
                "career_identity_id": row.career_identity_id,
                "career_identity_version": row.career_identity_version,
                "completeness_state": row.completeness_state,
                "sufficiency_state": row.sufficiency_state,
                "privacy_scope": row.privacy_scope,
                "context_payload": deepcopy(row.context_payload),
                "fact_refs": deepcopy(row.fact_refs),
                "created_at": _export_datetime(row.created_at),
                "updated_at": _export_datetime(row.updated_at),
            }
            for row in contexts
        ],
        "options": [
            {
                "option_id": row.option_id,
                "user_id": row.user_id,
                "decision_id": row.decision_id,
                "title": row.title,
                "description": row.description,
                "scenario": deepcopy(row.scenario),
                "status": row.status,
                "position": row.position,
                "created_at": _export_datetime(row.created_at),
                "updated_at": _export_datetime(row.updated_at),
            }
            for row in options
        ],
        "recommendations": [
            {
                "recommendation_id": row.recommendation_id,
                "user_id": row.user_id,
                "decision_id": row.decision_id,
                "context_snapshot_id": row.context_snapshot_id,
                "recommended_option_id": row.recommended_option_id,
                "recommendation_status": row.recommendation_status,
                "evidence_sufficiency": row.evidence_sufficiency,
                "confidence": row.confidence,
                "summary": row.summary,
                "fit_payload": deepcopy(row.fit_payload),
                "comparison_payload": deepcopy(row.comparison_payload),
                "evidence_payload": deepcopy(row.evidence_payload),
                "challenge_payload": deepcopy(row.challenge_payload),
                "limitations": deepcopy(row.limitations),
                "generated_at": _export_datetime(row.generated_at),
                "created_at": _export_datetime(row.created_at),
                "updated_at": _export_datetime(row.updated_at),
            }
            for row in recommendations
        ],
        "versions": [
            {
                "decision_version_id": row.decision_version_id,
                "user_id": row.user_id,
                "decision_id": row.decision_id,
                "version_number": row.version_number,
                "version_reason": row.version_reason,
                "decision_snapshot": deepcopy(row.decision_snapshot),
                "options_snapshot": deepcopy(row.options_snapshot),
                "recommendation_snapshot": deepcopy(row.recommendation_snapshot),
                "selected_option_id": row.selected_option_id,
                "context_snapshot_id": row.context_snapshot_id,
                "user_note": row.user_note,
                "created_at": _export_datetime(row.created_at),
                "updated_at": _export_datetime(row.updated_at),
            }
            for row in versions
        ],
        "action_plans": [
            {
                "action_plan_id": row.action_plan_id,
                "user_id": row.user_id,
                "decision_id": row.decision_id,
                "selected_option_id": row.selected_option_id,
                "title": row.title,
                "status": row.status,
                "plan_payload": deepcopy(row.plan_payload),
                "created_at": _export_datetime(row.created_at),
                "updated_at": _export_datetime(row.updated_at),
            }
            for row in plans
        ],
        "actions": [
            {
                "action_id": row.action_id,
                "user_id": row.user_id,
                "action_plan_id": row.action_plan_id,
                "decision_id": row.decision_id,
                "option_id": row.option_id,
                "action_type": row.action_type,
                "status": row.status,
                "title": row.title,
                "description": row.description,
                "due_at": _export_datetime(row.due_at),
                "priority": row.priority,
                "position": row.position,
                "completed_at": _export_datetime(row.completed_at),
                "metadata": deepcopy(row.metadata_json),
                "created_at": _export_datetime(row.created_at),
                "updated_at": _export_datetime(row.updated_at),
            }
            for row in actions
        ],
        "applications": [
            {
                "application_id": row.application_id,
                "user_id": row.user_id,
                "decision_id": row.decision_id,
                "action_id": row.action_id,
                "option_id": row.option_id,
                "company_id": row.company_id,
                "region_id": row.region_id,
                "role_title": row.role_title,
                "status": row.status,
                "status_started_at": _export_datetime(row.status_started_at),
                "applied_at": _export_datetime(row.applied_at),
                "follow_up_at": _export_datetime(row.follow_up_at),
                "source_url": row.source_url,
                "notes": row.notes,
                "metadata": deepcopy(row.metadata_json),
                "created_at": _export_datetime(row.created_at),
                "updated_at": _export_datetime(row.updated_at),
            }
            for row in applications
        ],
        "application_transitions": [
            {
                "transition_id": row.transition_id,
                "user_id": row.user_id,
                "application_id": row.application_id,
                "from_status": row.from_status,
                "to_status": row.to_status,
                "reason": row.reason,
                "metadata": deepcopy(row.metadata_json),
                "transitioned_at": _export_datetime(row.transitioned_at),
                "created_at": _export_datetime(row.created_at),
                "updated_at": _export_datetime(row.updated_at),
            }
            for row in transitions
        ],
        "outcomes": [
            {
                "outcome_id": row.outcome_id,
                "user_id": row.user_id,
                "decision_id": row.decision_id,
                "action_id": row.action_id,
                "application_id": row.application_id,
                "option_id": row.option_id,
                "recommendation_id": row.recommendation_id,
                "outcome_type": row.outcome_type,
                "status": row.status,
                "title": row.title,
                "description": row.description,
                "occurred_at": _export_datetime(row.occurred_at),
                "reflection": row.reflection,
                "evidence_payload": deepcopy(row.evidence_payload),
                "metadata": deepcopy(row.metadata_json),
                "created_at": _export_datetime(row.created_at),
                "updated_at": _export_datetime(row.updated_at),
            }
            for row in outcomes
        ],
    }


def _export_deep_decision_bundle(
    factors: list[Any],
    longitudinal_contexts: list[Any],
    evolutions: list[Any],
    findings: list[Any],
    reviews: list[Any],
) -> dict[str, Any]:
    return {
        "factors": [
            {
                "factor_id": row.factor_id,
                "user_id": row.user_id,
                "decision_id": row.decision_id,
                "option_id": row.option_id,
                "recommendation_id": row.recommendation_id,
                "context_snapshot_id": row.context_snapshot_id,
                "domain": row.domain,
                "category": row.category,
                "factor_key": row.factor_key,
                "label": row.label,
                "normalized_value": deepcopy(row.normalized_value),
                "raw_value": deepcopy(row.raw_value),
                "direction": row.direction,
                "importance": row.importance,
                "confidence": row.confidence,
                "uncertainty": row.uncertainty,
                "evidence_strength": row.evidence_strength,
                "evidence_kind": row.evidence_kind,
                "source_type": row.source_type,
                "source_id": row.source_id,
                "provenance": deepcopy(row.provenance),
                "explanation": row.explanation,
                "caveats": deepcopy(row.caveats),
                "freshness_status": row.freshness_status,
                "freshness_expires_at": _export_datetime(row.freshness_expires_at),
                "generated_at": _export_datetime(row.generated_at),
                "created_at": _export_datetime(row.created_at),
                "updated_at": _export_datetime(row.updated_at),
            }
            for row in factors
        ],
        "longitudinal_contexts": [
            {
                "longitudinal_context_id": row.longitudinal_context_id,
                "user_id": row.user_id,
                "decision_id": row.decision_id,
                "window_start": _export_datetime(row.window_start),
                "window_end": _export_datetime(row.window_end),
                "record_count": row.record_count,
                "context_payload": deepcopy(row.context_payload),
                "evidence_payload": deepcopy(row.evidence_payload),
                "generated_at": _export_datetime(row.generated_at),
                "created_at": _export_datetime(row.created_at),
                "updated_at": _export_datetime(row.updated_at),
            }
            for row in longitudinal_contexts
        ],
        "recommendation_evolutions": [
            {
                "evolution_id": row.evolution_id,
                "user_id": row.user_id,
                "decision_id": row.decision_id,
                "previous_recommendation_id": row.previous_recommendation_id,
                "current_recommendation_id": row.current_recommendation_id,
                "change_type": row.change_type,
                "meaningful_changes": deepcopy(row.meaningful_changes),
                "confidence_before": row.confidence_before,
                "confidence_after": row.confidence_after,
                "evidence_basis": deepcopy(row.evidence_basis),
                "uncertainty": row.uncertainty,
                "explanation": row.explanation,
                "generated_at": _export_datetime(row.generated_at),
                "created_at": _export_datetime(row.created_at),
                "updated_at": _export_datetime(row.updated_at),
            }
            for row in evolutions
        ],
        "advisory_findings": [
            {
                "advisory_finding_id": row.advisory_finding_id,
                "user_id": row.user_id,
                "decision_id": row.decision_id,
                "finding_type": row.finding_type,
                "severity": row.severity,
                "support_status": row.support_status,
                "confidence": row.confidence,
                "uncertainty": row.uncertainty,
                "window_start": _export_datetime(row.window_start),
                "window_end": _export_datetime(row.window_end),
                "affected_goal": row.affected_goal,
                "supporting_evidence": deepcopy(row.supporting_evidence),
                "counter_evidence": deepcopy(row.counter_evidence),
                "explanation": row.explanation,
                "suggested_action": row.suggested_action,
                "acknowledged_at": _export_datetime(row.acknowledged_at),
                "dismissed_at": _export_datetime(row.dismissed_at),
                "generated_at": _export_datetime(row.generated_at),
                "created_at": _export_datetime(row.created_at),
                "updated_at": _export_datetime(row.updated_at),
            }
            for row in findings
        ],
        "strategic_reviews": [
            {
                "strategic_review_id": row.strategic_review_id,
                "user_id": row.user_id,
                "decision_id": row.decision_id,
                "longitudinal_context_id": row.longitudinal_context_id,
                "status": row.status,
                "window_start": _export_datetime(row.window_start),
                "window_end": _export_datetime(row.window_end),
                "goals": deepcopy(row.goals),
                "strategy_performance": deepcopy(row.strategy_performance),
                "application_summary": deepcopy(row.application_summary),
                "outcome_summary": deepcopy(row.outcome_summary),
                "identity_changes": deepcopy(row.identity_changes),
                "market_changes": deepcopy(row.market_changes),
                "recommendation_changes": deepcopy(row.recommendation_changes),
                "active_risks": deepcopy(row.active_risks),
                "blind_spots": deepcopy(row.blind_spots),
                "suggested_next_actions": deepcopy(row.suggested_next_actions),
                "confidence": row.confidence,
                "uncertainty": row.uncertainty,
                "generated_at": _export_datetime(row.generated_at),
                "created_at": _export_datetime(row.created_at),
                "updated_at": _export_datetime(row.updated_at),
            }
            for row in reviews
        ],
    }


def _new_saved_artifact_id() -> str:
    return f"saved_artifact_{uuid4().hex[:47]}"


def _new_recommendation_snapshot_id() -> str:
    return f"recommendation_snapshot_{uuid4().hex[:40]}"
