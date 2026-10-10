"""Thin data-access layer for internal app-user identity tables."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from backend.alerts.models import UserAlert
from backend.career_agent.models import (
    CareerAgentToolAuditEventRecord,
    CareerAgentToolRecord,
    CareerMemoryEntryRecord,
    CareerMemoryPermissionRecord,
)
from backend.career_decisions.models import (
    CareerAction,
    CareerActionPlan,
    CareerApplication,
    CareerApplicationTransition,
    CareerDecision,
    CareerOutcome,
    DecisionContextSnapshot,
    DecisionOption,
    DecisionRecommendation,
    DecisionVersion,
)
from backend.career_identity.models import (
    CareerIdentity,
    CareerIdentityFact,
    CareerIdentityImport,
)
from backend.deep_decisions.models import (
    AdvisoryFinding,
    DecisionFactor,
    LongitudinalContextSnapshot,
    RecommendationEvolution,
    StrategicCareerReview,
)
from backend.explore.models import ExploreComparisonSnapshot, ExploreDecisionProvenance
from backend.product_measurement.models import (
    BetaCohortMembership,
    CommercialExperimentSignal,
    DecisionReflection,
    ExperimentAssignment,
    ProductAnalyticsEvent,
    ProductEntitlementGrant,
    ProductUserVisit,
    RecommendationFeedback,
    StrategyChange,
    SupportCase,
    SupportCaseEvent,
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

    @property
    def session(self) -> Session:
        return self._session

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

    def get_saved_market_artifact(self, saved_artifact_id: str) -> SavedMarketArtifact | None:
        return self._session.get(SavedMarketArtifact, saved_artifact_id)

    def get_saved_market_artifact_by_identity(
        self,
        *,
        user_id: str,
        artifact_type: str,
        artifact_ref: str,
    ) -> SavedMarketArtifact | None:
        return self._session.scalar(
            select(SavedMarketArtifact).where(
                SavedMarketArtifact.user_id == user_id,
                SavedMarketArtifact.artifact_type == artifact_type,
                SavedMarketArtifact.artifact_ref == artifact_ref,
            )
        )

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
                select(CareerMemoryEntryRecord).where(CareerMemoryEntryRecord.user_id == user_id)
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

    def list_career_memory_permissions_for_user(
        self,
        user_id: str,
    ) -> list[CareerMemoryPermissionRecord]:
        rows = self._session.execute(
            select(CareerMemoryPermissionRecord)
            .where(CareerMemoryPermissionRecord.user_id == user_id)
            .order_by(CareerMemoryPermissionRecord.category)
        ).scalars()
        return list(rows)

    def list_career_memory_entries_for_user(
        self,
        user_id: str,
    ) -> list[CareerMemoryEntryRecord]:
        rows = self._session.execute(
            select(CareerMemoryEntryRecord)
            .where(CareerMemoryEntryRecord.user_id == user_id)
            .order_by(
                CareerMemoryEntryRecord.category,
                CareerMemoryEntryRecord.value,
                CareerMemoryEntryRecord.career_memory_entry_id,
            )
        ).scalars()
        return list(rows)

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
                select(CareerAgentToolRecord).where(CareerAgentToolRecord.user_id == user_id)
            ).scalars()
        )
        for row in (*audit_rows, *tool_rows):
            self._session.delete(row)
        return len(audit_rows) + len(tool_rows)

    def list_career_agent_tool_records_for_user(
        self,
        user_id: str,
    ) -> list[CareerAgentToolRecord]:
        rows = self._session.execute(
            select(CareerAgentToolRecord)
            .where(CareerAgentToolRecord.user_id == user_id)
            .order_by(
                CareerAgentToolRecord.created_at,
                CareerAgentToolRecord.career_agent_tool_id,
            )
        ).scalars()
        return list(rows)

    def list_career_agent_tool_audit_events_for_user(
        self,
        user_id: str,
    ) -> list[CareerAgentToolAuditEventRecord]:
        rows = self._session.execute(
            select(CareerAgentToolAuditEventRecord)
            .where(CareerAgentToolAuditEventRecord.user_id == user_id)
            .order_by(
                CareerAgentToolAuditEventRecord.created_at,
                CareerAgentToolAuditEventRecord.career_agent_tool_id,
            )
        ).scalars()
        return list(rows)

    def get_career_identity_for_user(self, user_id: str) -> CareerIdentity | None:
        return self._session.execute(
            select(CareerIdentity).where(CareerIdentity.user_id == user_id)
        ).scalar_one_or_none()

    def list_career_identity_facts_for_user(
        self,
        user_id: str,
    ) -> list[CareerIdentityFact]:
        rows = self._session.execute(
            select(CareerIdentityFact)
            .where(CareerIdentityFact.user_id == user_id)
            .order_by(
                CareerIdentityFact.fact_type,
                CareerIdentityFact.created_at,
                CareerIdentityFact.career_identity_fact_id,
            )
        ).scalars()
        return list(rows)

    def list_career_identity_imports_for_user(
        self,
        user_id: str,
    ) -> list[CareerIdentityImport]:
        rows = self._session.execute(
            select(CareerIdentityImport)
            .where(CareerIdentityImport.user_id == user_id)
            .order_by(
                CareerIdentityImport.created_at,
                CareerIdentityImport.career_identity_import_id,
            )
        ).scalars()
        return list(rows)

    def delete_career_identity_for_user(self, user_id: str) -> tuple[int, int, int]:
        facts = self.list_career_identity_facts_for_user(user_id)
        imports = self.list_career_identity_imports_for_user(user_id)
        identity = self.get_career_identity_for_user(user_id)
        for fact in facts:
            self._session.delete(fact)
        self._session.flush()
        for row in imports:
            self._session.delete(row)
        self._session.flush()
        deleted_identity = 0
        if identity is not None:
            self._session.delete(identity)
            deleted_identity = 1
        return deleted_identity, len(facts), len(imports)

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

    def list_career_decisions_for_user(self, user_id: str) -> list[CareerDecision]:
        return list(
            self._session.execute(
                select(CareerDecision)
                .where(CareerDecision.user_id == user_id)
                .order_by(CareerDecision.created_at, CareerDecision.decision_id)
            ).scalars()
        )

    def list_decision_context_snapshots_for_user(
        self, user_id: str
    ) -> list[DecisionContextSnapshot]:
        return list(
            self._session.execute(
                select(DecisionContextSnapshot)
                .where(DecisionContextSnapshot.user_id == user_id)
                .order_by(
                    DecisionContextSnapshot.created_at,
                    DecisionContextSnapshot.context_snapshot_id,
                )
            ).scalars()
        )

    def list_decision_options_for_user(self, user_id: str) -> list[DecisionOption]:
        return list(
            self._session.execute(
                select(DecisionOption)
                .where(DecisionOption.user_id == user_id)
                .order_by(DecisionOption.created_at, DecisionOption.option_id)
            ).scalars()
        )

    def list_decision_recommendations_for_user(self, user_id: str) -> list[DecisionRecommendation]:
        return list(
            self._session.execute(
                select(DecisionRecommendation)
                .where(DecisionRecommendation.user_id == user_id)
                .order_by(
                    DecisionRecommendation.generated_at,
                    DecisionRecommendation.recommendation_id,
                )
            ).scalars()
        )

    def list_decision_versions_for_user(self, user_id: str) -> list[DecisionVersion]:
        return list(
            self._session.execute(
                select(DecisionVersion)
                .where(DecisionVersion.user_id == user_id)
                .order_by(DecisionVersion.created_at, DecisionVersion.decision_version_id)
            ).scalars()
        )

    def list_career_action_plans_for_user(self, user_id: str) -> list[CareerActionPlan]:
        return list(
            self._session.execute(
                select(CareerActionPlan)
                .where(CareerActionPlan.user_id == user_id)
                .order_by(CareerActionPlan.created_at, CareerActionPlan.action_plan_id)
            ).scalars()
        )

    def list_career_actions_for_user(self, user_id: str) -> list[CareerAction]:
        return list(
            self._session.execute(
                select(CareerAction)
                .where(CareerAction.user_id == user_id)
                .order_by(CareerAction.created_at, CareerAction.action_id)
            ).scalars()
        )

    def list_career_applications_for_user(self, user_id: str) -> list[CareerApplication]:
        return list(
            self._session.execute(
                select(CareerApplication)
                .where(CareerApplication.user_id == user_id)
                .order_by(CareerApplication.created_at, CareerApplication.application_id)
            ).scalars()
        )

    def list_career_application_transitions_for_user(
        self, user_id: str
    ) -> list[CareerApplicationTransition]:
        return list(
            self._session.execute(
                select(CareerApplicationTransition)
                .where(CareerApplicationTransition.user_id == user_id)
                .order_by(
                    CareerApplicationTransition.transitioned_at,
                    CareerApplicationTransition.transition_id,
                )
            ).scalars()
        )

    def list_career_outcomes_for_user(self, user_id: str) -> list[CareerOutcome]:
        return list(
            self._session.execute(
                select(CareerOutcome)
                .where(CareerOutcome.user_id == user_id)
                .order_by(CareerOutcome.occurred_at, CareerOutcome.outcome_id)
            ).scalars()
        )

    def list_decision_factors_for_user(self, user_id: str) -> list[DecisionFactor]:
        return list(
            self._session.execute(
                select(DecisionFactor)
                .where(DecisionFactor.user_id == user_id)
                .order_by(DecisionFactor.generated_at, DecisionFactor.factor_id)
            ).scalars()
        )

    def list_longitudinal_context_snapshots_for_user(
        self, user_id: str
    ) -> list[LongitudinalContextSnapshot]:
        return list(
            self._session.execute(
                select(LongitudinalContextSnapshot)
                .where(LongitudinalContextSnapshot.user_id == user_id)
                .order_by(
                    LongitudinalContextSnapshot.generated_at,
                    LongitudinalContextSnapshot.longitudinal_context_id,
                )
            ).scalars()
        )

    def list_recommendation_evolutions_for_user(
        self, user_id: str
    ) -> list[RecommendationEvolution]:
        return list(
            self._session.execute(
                select(RecommendationEvolution)
                .where(RecommendationEvolution.user_id == user_id)
                .order_by(
                    RecommendationEvolution.generated_at,
                    RecommendationEvolution.evolution_id,
                )
            ).scalars()
        )

    def list_advisory_findings_for_user(self, user_id: str) -> list[AdvisoryFinding]:
        return list(
            self._session.execute(
                select(AdvisoryFinding)
                .where(AdvisoryFinding.user_id == user_id)
                .order_by(AdvisoryFinding.generated_at, AdvisoryFinding.advisory_finding_id)
            ).scalars()
        )

    def list_strategic_career_reviews_for_user(self, user_id: str) -> list[StrategicCareerReview]:
        return list(
            self._session.execute(
                select(StrategicCareerReview)
                .where(StrategicCareerReview.user_id == user_id)
                .order_by(
                    StrategicCareerReview.generated_at,
                    StrategicCareerReview.strategic_review_id,
                )
            ).scalars()
        )

    def delete_deep_decision_data_for_user(self, user_id: str) -> int:
        return self._delete_user_rows(
            user_id,
            StrategicCareerReview,
            AdvisoryFinding,
            RecommendationEvolution,
            DecisionFactor,
            LongitudinalContextSnapshot,
        )

    def delete_product_measurement_data_for_user(self, user_id: str) -> int:
        """Delete current-user measurement overlays before their referenced objects."""
        support_case_ids = select(SupportCase.support_case_id).where(SupportCase.user_id == user_id)
        support_events = (
            self._session.execute(
                delete(SupportCaseEvent).where(
                    SupportCaseEvent.support_case_id.in_(support_case_ids)
                )
            ).rowcount
            or 0
        )
        return support_events + self._delete_user_rows(
            user_id,
            # Visits can reference the append-only analytics events deleted below.
            ProductUserVisit,
            # These records can reference the Decision graph deleted later.
            RecommendationFeedback,
            DecisionReflection,
            StrategyChange,
            SupportCase,
            BetaCohortMembership,
            ExperimentAssignment,
            ProductEntitlementGrant,
            CommercialExperimentSignal,
            # Privacy deletion is the explicit lifecycle exception to append-only
            # analytics retention. A bulk delete intentionally bypasses ORM guards.
            ProductAnalyticsEvent,
        )

    def delete_career_decision_data_for_user(self, user_id: str) -> int:
        for decision in self.list_career_decisions_for_user(user_id):
            decision.current_context_snapshot_id = None
            decision.current_recommendation_id = None
            decision.selected_option_id = None
        self._session.flush()
        return self._delete_user_rows(
            user_id,
            CareerOutcome,
            CareerApplicationTransition,
            CareerApplication,
            CareerAction,
            CareerActionPlan,
            DecisionVersion,
            DecisionRecommendation,
            DecisionOption,
            DecisionContextSnapshot,
            CareerDecision,
        )

    def list_explore_comparisons_for_user(self, user_id: str) -> list[ExploreComparisonSnapshot]:
        return list(
            self._session.execute(
                select(ExploreComparisonSnapshot)
                .where(ExploreComparisonSnapshot.user_id == user_id)
                .order_by(
                    ExploreComparisonSnapshot.generated_at,
                    ExploreComparisonSnapshot.comparison_id,
                )
            ).scalars()
        )

    def list_explore_decision_provenance_for_user(
        self, user_id: str
    ) -> list[ExploreDecisionProvenance]:
        return list(
            self._session.execute(
                select(ExploreDecisionProvenance)
                .where(ExploreDecisionProvenance.user_id == user_id)
                .order_by(
                    ExploreDecisionProvenance.created_at,
                    ExploreDecisionProvenance.provenance_id,
                )
            ).scalars()
        )

    def delete_explore_comparison_data_for_user(self, user_id: str) -> int:
        return self._delete_user_rows(
            user_id,
            ExploreDecisionProvenance,
            ExploreComparisonSnapshot,
        )

    def delete_preference_profile(self, profile: UserPreferenceProfile) -> None:
        self._session.delete(profile)

    def delete_profile(self, profile: UserProfile) -> None:
        self._session.delete(profile)

    def delete_external_identities_for_user(self, user_id: str) -> int:
        identities = self.list_external_identities(user_id)
        for identity in identities:
            self._session.delete(identity)
        return len(identities)

    def scrub_external_identities_for_deactivated_user(self, user_id: str) -> int:
        identities = self.list_external_identities(user_id)
        scrubbed_at = datetime.now(UTC)
        for identity in identities:
            identity.email = None
            identity.email_verified = None
            identity.last_seen_at = scrubbed_at
        return len(identities)

    def flush(self) -> None:
        self._session.flush()

    def _delete_user_rows(self, user_id: str, *models: type) -> int:
        deleted = 0
        for model in models:
            result = self._session.execute(delete(model).where(model.user_id == user_id))
            deleted += result.rowcount or 0
        return deleted
