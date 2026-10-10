"""Layer 40A measurement, beta, support, and entitlement services."""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy.orm import Session

from backend.admin.repository import AdminEventLogRepository
from backend.admin.roles import AdminRole
from backend.admin.service import AdminEventLogInput, AdminEventLogService
from backend.career_decisions.models import (
    CareerAction,
    CareerApplication,
    CareerDecision,
    CareerOutcome,
    DecisionRecommendation,
)
from backend.career_identity.models import CareerIdentity
from backend.monetization.enforcement import evaluate_account_access
from backend.monetization.repository import MonetizationRepository
from backend.product_measurement.models import (
    BetaCohort,
    BetaCohortMembership,
    CommercialExperimentSignal,
    DecisionReflection,
    ExperimentAssignment,
    ProductAnalyticsEvent,
    ProductEntitlementGrant,
    ProductFeatureGate,
    ProductUserVisit,
    RecommendationFeedback,
    StrategyChange,
    SupportCase,
    SupportCaseEvent,
)
from backend.product_measurement.repository import ProductMeasurementRepository
from backend.product_measurement.schemas import (
    BetaAnalyticsSummary,
    CohortCreate,
    CohortMembershipCreate,
    CohortMembershipStatus,
    CohortMembershipView,
    CohortStatus,
    CohortView,
    CommercialExperimentSignalCreate,
    CommercialExperimentSignalView,
    CommercialSignalType,
    DecisionReflectionCreate,
    DecisionReflectionView,
    EntitlementGrantCreate,
    EntitlementGrantView,
    ExperimentAssignmentCreate,
    ExperimentAssignmentView,
    FeatureAccessDecision,
    FeatureAccessMode,
    FeatureGateCreate,
    FeatureGateView,
    FunnelStageCount,
    ProductEventCreate,
    ProductEventSource,
    ProductEventType,
    ProductEventView,
    RecommendationFeedbackCreate,
    RecommendationFeedbackView,
    StrategyChangeCreate,
    StrategyChangeView,
    SupportCaseCreate,
    SupportCaseStatus,
    SupportCaseType,
    SupportCaseUpdate,
    SupportCaseView,
)
from backend.users.exceptions import CrossUserAccessBlocked, UserNotFound
from backend.users.models import User

FUNNEL_STAGES: tuple[tuple[str, tuple[ProductEventType, ...]], ...] = (
    ("signed_in", (ProductEventType.AUTHENTICATED_VISIT,)),
    ("profile_essentials_sufficient", (ProductEventType.CAREER_IDENTITY_SUFFICIENT,)),
    (
        "explore_viewed",
        (
            ProductEventType.EXPLORE_CONTEXT_EVALUATED,
            ProductEventType.EXPLORE_FIT_GENERATED,
            ProductEventType.EXPLORE_FIT_ABSTAINED,
        ),
    ),
    ("market_inspected", (ProductEventType.MARKET_INSPECTED,)),
    ("two_plus_markets_selected", (ProductEventType.COMPARISON_SELECTION_READY,)),
    ("comparison_generated", (ProductEventType.COMPARISON_GENERATED,)),
    (
        "comparison_saved_or_prioritized",
        (ProductEventType.COMPARISON_SAVED, ProductEventType.PRIORITIZE_COMPLETED),
    ),
    ("my_search_viewed", (ProductEventType.MY_SEARCH_VIEWED,)),
    ("action_completed", (ProductEventType.ACTION_SUCCEEDED,)),
    ("application_tracking_started", (ProductEventType.APPLICATION_RECORDED,)),
    ("return", (ProductEventType.USER_RETURNED,)),
)

CAUSAL_LIMITATION = (
    "Observed outcomes are beta evidence for association and product usefulness; "
    "they do not establish that a recommendation caused an application, interview, "
    "offer, or other outcome."
)
RETURN_VISIT_INACTIVITY_GAP = timedelta(minutes=30)


class ProductMeasurementNotFound(Exception):
    pass


class ProductMeasurementValidationError(Exception):
    pass


class ProductMeasurementService:
    def __init__(
        self,
        session: Session,
        *,
        clock: callable | None = None,
    ) -> None:
        self._session = session
        self._repo = ProductMeasurementRepository(session)
        self._admin_events = AdminEventLogService(AdminEventLogRepository(session))
        self._clock = clock or (lambda: datetime.now(UTC))

    def record_event(
        self,
        user_id: str | None,
        request: ProductEventCreate,
    ) -> ProductAnalyticsEvent:
        if user_id is not None:
            self._ensure_user(user_id)
        self._validate_event_ownership(user_id, request)
        cohort_key = request.cohort_key
        experiment_key = request.experiment_key
        variant_key = request.variant_key
        if user_id is not None and cohort_key is None:
            active_memberships = sorted(
                self._active_memberships(user_id),
                key=lambda item: item[0].cohort_key,
            )
            if active_memberships:
                cohort_key = active_memberships[0][0].cohort_key
        if user_id is not None and (experiment_key is None or variant_key is None):
            assignments = [
                assignment
                for assignment in self._repo.list_assignments(user_id=user_id, limit=100)
                if assignment.status == "assigned"
                and (assignment.expires_at is None or _aware(assignment.expires_at) > self._clock())
            ]
            if len(assignments) == 1:
                experiment_key = experiment_key or assignments[0].experiment_key
                variant_key = variant_key or assignments[0].variant_key
        row = ProductAnalyticsEvent(
            event_id=_new_id("product_event"),
            user_id=user_id,
            anonymous_session_id=request.anonymous_session_id,
            event_type=request.event_type.value,
            schema_version=request.schema_version,
            occurred_at=request.occurred_at or self._clock(),
            event_source=request.event_source.value,
            product_surface=request.product_surface,
            decision_id=request.decision_id,
            recommendation_id=request.recommendation_id,
            current_opportunity_id=request.current_opportunity_id,
            action_id=request.action_id,
            application_id=request.application_id,
            outcome_id=request.outcome_id,
            career_identity_id=request.career_identity_id,
            career_identity_version=request.career_identity_version,
            cohort_key=cohort_key,
            experiment_key=experiment_key,
            variant_key=variant_key,
            confidence_bucket=request.confidence_bucket,
            coverage_status=request.coverage_status,
            recommendation_state=request.recommendation_state,
            payload=deepcopy(request.payload),
            created_at=self._clock(),
        )
        self._repo.add(row)
        self._repo.flush()
        return row

    def best_effort_record_event(
        self,
        user_id: str | None,
        request: ProductEventCreate,
    ) -> ProductAnalyticsEvent | None:
        try:
            return self.record_event(user_id, request)
        except Exception:
            return None

    def observe_authenticated_product_visit(
        self,
        user_id: str,
        *,
        product_surface: str = "authenticated_app",
        occurred_at: datetime | None = None,
    ) -> ProductUserVisit:
        """Record an authenticated product visit and emit one later-return event.

        A return is the first authenticated product bootstrap after the user's
        prior recorded visit has been inactive for the configured gap.
        """

        self._ensure_user(user_id)
        now = occurred_at or self._clock()
        active_memberships = sorted(
            self._active_memberships(user_id),
            key=lambda item: item[0].cohort_key,
        )
        assignments = sorted(
            (
                assignment
                for assignment in self._repo.list_assignments(user_id=user_id, limit=100)
                if assignment.status == "assigned"
                and (assignment.expires_at is None or _aware(assignment.expires_at) > now)
            ),
            key=lambda assignment: (assignment.experiment_key, assignment.variant_key),
        )
        cohort_keys = tuple(cohort.cohort_key for cohort, _membership in active_memberships)
        primary_cohort_key = cohort_keys[0] if cohort_keys else None
        primary_assignment = assignments[0] if len(assignments) == 1 else None

        latest = self._repo.get_latest_visit(user_id)
        if latest is not None and _aware(latest.last_seen_at) + RETURN_VISIT_INACTIVITY_GAP > now:
            latest.last_seen_at = now
            latest.updated_at = now
            self._repo.flush()
            return latest

        visit = ProductUserVisit(
            visit_id=_new_id("product_visit"),
            user_id=user_id,
            visit_started_at=now,
            last_seen_at=now,
            product_surface=product_surface,
            cohort_key=primary_cohort_key,
            experiment_key=primary_assignment.experiment_key if primary_assignment else None,
            variant_key=primary_assignment.variant_key if primary_assignment else None,
            created_at=now,
            updated_at=now,
        )
        self._repo.add(visit)
        self._repo.flush()
        self.record_event(
            user_id,
            ProductEventCreate(
                event_type=ProductEventType.AUTHENTICATED_VISIT,
                event_source=ProductEventSource.BACKEND,
                product_surface=product_surface,
                cohort_key=primary_cohort_key,
                experiment_key=primary_assignment.experiment_key if primary_assignment else None,
                variant_key=primary_assignment.variant_key if primary_assignment else None,
                payload={"visit_id": visit.visit_id},
            ),
        )
        if latest is None:
            return visit

        event = self.record_event(
            user_id,
            ProductEventCreate(
                event_type=ProductEventType.USER_RETURNED,
                event_source=ProductEventSource.BACKEND,
                product_surface=product_surface,
                cohort_key=primary_cohort_key,
                experiment_key=primary_assignment.experiment_key if primary_assignment else None,
                variant_key=primary_assignment.variant_key if primary_assignment else None,
                payload={
                    "return_definition": "authenticated_visit_after_30_minutes_inactivity",
                    "previous_visit_id": latest.visit_id,
                    "current_visit_id": visit.visit_id,
                    "minutes_since_last_seen": int(
                        (now - _aware(latest.last_seen_at)).total_seconds() // 60
                    ),
                    "cohort_keys": list(cohort_keys),
                    "experiment_assignments": [
                        {
                            "experiment_key": assignment.experiment_key,
                            "variant_key": assignment.variant_key,
                        }
                        for assignment in assignments
                    ],
                },
            ),
        )
        visit.returned_event_id = event.event_id
        self._repo.flush()
        return visit

    def submit_recommendation_feedback(
        self,
        user_id: str,
        request: RecommendationFeedbackCreate,
    ) -> RecommendationFeedback:
        recommendation = self._owned_recommendation(user_id, request.recommendation_id)
        if recommendation.decision_id != request.decision_id:
            raise ProductMeasurementValidationError(
                "feedback recommendation does not match decision"
            )
        row = RecommendationFeedback(
            feedback_id=_new_id("rec_feedback"),
            user_id=user_id,
            decision_id=request.decision_id,
            recommendation_id=request.recommendation_id,
            useful=request.useful,
            surprising=request.surprising,
            changed_decision=request.changed_decision,
            missing_alternative=request.missing_alternative,
            missing_alternative_category=request.missing_alternative_category,
            confidence_calibration=request.confidence_calibration.value,
            feedback_comment=request.feedback_comment,
            cohort_key=request.cohort_key,
            experiment_key=request.experiment_key,
            variant_key=request.variant_key,
            created_at=self._clock(),
            updated_at=self._clock(),
        )
        self._repo.add(row)
        self._repo.flush()
        self.record_event(
            user_id,
            ProductEventCreate(
                event_type=ProductEventType.RECOMMENDATION_FEEDBACK_SUBMITTED,
                event_source=ProductEventSource.BACKEND,
                decision_id=request.decision_id,
                recommendation_id=request.recommendation_id,
                cohort_key=request.cohort_key,
                experiment_key=request.experiment_key,
                variant_key=request.variant_key,
                confidence_bucket=recommendation.confidence,
                coverage_status=recommendation.evidence_sufficiency,
                recommendation_state=recommendation.recommendation_status,
                payload={
                    "useful": request.useful,
                    "surprising": request.surprising,
                    "changed_decision": request.changed_decision,
                    "missing_alternative": request.missing_alternative,
                    "confidence_calibration": request.confidence_calibration.value,
                },
            ),
        )
        if request.changed_decision:
            self.record_event(
                user_id,
                ProductEventCreate(
                    event_type=ProductEventType.RECOMMENDATION_CHANGED_DECISION,
                    event_source=ProductEventSource.BACKEND,
                    decision_id=request.decision_id,
                    recommendation_id=request.recommendation_id,
                    cohort_key=request.cohort_key,
                    experiment_key=request.experiment_key,
                    variant_key=request.variant_key,
                    confidence_bucket=recommendation.confidence,
                    coverage_status=recommendation.evidence_sufficiency,
                    recommendation_state=recommendation.recommendation_status,
                ),
            )
        return row

    def list_my_feedback(self, user_id: str) -> list[RecommendationFeedback]:
        self._ensure_user(user_id)
        return self._repo.list_recommendation_feedback(user_id=user_id)

    def record_reflection(
        self,
        user_id: str,
        request: DecisionReflectionCreate,
    ) -> DecisionReflection:
        self._owned_decision(user_id, request.decision_id)
        if request.recommendation_id is not None:
            self._owned_recommendation(user_id, request.recommendation_id)
        if request.outcome_id is not None:
            self._owned_outcome(user_id, request.outcome_id)
        row = DecisionReflection(
            reflection_id=_new_id("decision_reflection"),
            user_id=user_id,
            decision_id=request.decision_id,
            recommendation_id=request.recommendation_id,
            outcome_id=request.outcome_id,
            would_make_same_decision=request.would_make_same_decision.value,
            view_changed=request.view_changed,
            satisfaction_rating=request.satisfaction_rating,
            regret_level=request.regret_level.value if request.regret_level else None,
            reflection_comment=request.reflection_comment,
            created_at=self._clock(),
            updated_at=self._clock(),
        )
        self._repo.add(row)
        self._repo.flush()
        self.record_event(
            user_id,
            ProductEventCreate(
                event_type=ProductEventType.REFLECTION_RECORDED,
                event_source=ProductEventSource.BACKEND,
                decision_id=request.decision_id,
                recommendation_id=request.recommendation_id,
                outcome_id=request.outcome_id,
                payload={
                    "would_make_same_decision": request.would_make_same_decision.value,
                    "view_changed": request.view_changed,
                    "satisfaction_rating": request.satisfaction_rating,
                    "regret_level": request.regret_level.value if request.regret_level else None,
                },
            ),
        )
        return row

    def record_strategy_change(
        self,
        user_id: str,
        request: StrategyChangeCreate,
    ) -> StrategyChange:
        self._ensure_user(user_id)
        if request.decision_id is not None:
            self._owned_decision(user_id, request.decision_id)
        if request.recommendation_id is not None:
            self._owned_recommendation(user_id, request.recommendation_id)
        row = StrategyChange(
            strategy_change_id=_new_id("strategy_change"),
            user_id=user_id,
            decision_id=request.decision_id,
            recommendation_id=request.recommendation_id,
            change_type=request.change_type.value,
            previous_state=deepcopy(request.previous_state),
            new_state=deepcopy(request.new_state),
            reason_category=request.reason_category,
            occurred_at=request.occurred_at or self._clock(),
            note=request.note,
            created_at=self._clock(),
            updated_at=self._clock(),
        )
        self._repo.add(row)
        self._repo.flush()
        self.record_event(
            user_id,
            ProductEventCreate(
                event_type=ProductEventType.STRATEGY_CHANGED,
                event_source=ProductEventSource.BACKEND,
                decision_id=request.decision_id,
                recommendation_id=request.recommendation_id,
                payload={
                    "change_type": request.change_type.value,
                    "reason_category": request.reason_category,
                },
            ),
        )
        return row

    def create_support_case(self, user_id: str, request: SupportCaseCreate) -> SupportCase:
        self._ensure_user(user_id)
        self._validate_support_links(user_id, request)
        row = SupportCase(
            support_case_id=_new_id("support_case"),
            user_id=user_id,
            case_type=request.case_type.value,
            status=SupportCaseStatus.OPEN.value,
            title=request.title,
            description=request.description,
            subject_type=request.subject_type,
            subject_id=request.subject_id,
            decision_id=request.decision_id,
            recommendation_id=request.recommendation_id,
            current_opportunity_id=request.current_opportunity_id,
            privacy_request_type=request.privacy_request_type,
            priority=request.priority,
            created_at=self._clock(),
            updated_at=self._clock(),
        )
        self._repo.add(row)
        self._repo.flush()
        self._add_support_event(row, actor_user_id=user_id, event_type="created")
        self.record_event(
            user_id,
            ProductEventCreate(
                event_type=ProductEventType.SUPPORT_CASE_CREATED,
                event_source=ProductEventSource.BACKEND,
                product_surface="support",
                decision_id=request.decision_id,
                recommendation_id=request.recommendation_id,
                current_opportunity_id=request.current_opportunity_id,
                payload={"case_type": request.case_type.value, "priority": request.priority},
            ),
        )
        return row

    def list_support_cases(self, user_id: str) -> list[SupportCase]:
        self._ensure_user(user_id)
        return self._repo.list_support_cases(user_id=user_id)

    def admin_list_support_cases(
        self,
        *,
        status: SupportCaseStatus | None = None,
        case_type: SupportCaseType | None = None,
        limit: int = 500,
    ) -> list[SupportCase]:
        return self._repo.list_support_cases(
            status=status.value if status else None,
            case_type=case_type.value if case_type else None,
            limit=limit,
        )

    def update_support_case(
        self,
        support_case_id: str,
        request: SupportCaseUpdate,
        *,
        actor_user_id: str,
        role: AdminRole,
    ) -> SupportCase:
        row = self._repo.get_support_case(support_case_id)
        if row is None:
            raise ProductMeasurementNotFound(support_case_id)
        before = _support_case_state(row)
        row.status = request.status.value
        row.assigned_operator_id = request.assigned_operator_id or row.assigned_operator_id
        if request.resolution is not None:
            row.resolution = request.resolution
        if request.status is SupportCaseStatus.RESOLVED and row.resolved_at is None:
            row.resolved_at = self._clock()
        if request.status is SupportCaseStatus.CLOSED and row.closed_at is None:
            row.closed_at = self._clock()
        row.updated_at = self._clock()
        self._repo.flush()
        after = _support_case_state(row)
        self._add_support_event(
            row,
            actor_user_id=actor_user_id,
            event_type="status_changed",
            before_state=before,
            after_state=after,
            note=request.note,
        )
        self.record_event(
            row.user_id,
            ProductEventCreate(
                event_type=ProductEventType.SUPPORT_CASE_STATUS_CHANGED,
                event_source=ProductEventSource.ADMIN,
                product_surface="support_admin",
                decision_id=row.decision_id,
                recommendation_id=row.recommendation_id,
                current_opportunity_id=row.current_opportunity_id,
                payload={"case_type": row.case_type, "status": row.status},
            ),
        )
        self._admin_events.record_event(
            AdminEventLogInput(
                actor=actor_user_id,
                role=role,
                action="admin.support_case.status_changed",
                object_type="support_case",
                object_id=support_case_id,
                before_state=before,
                after_state=after,
                reason=request.note or f"set support case status to {row.status}",
            )
        )
        return row

    def upsert_cohort(
        self,
        request: CohortCreate,
        *,
        actor_user_id: str,
        role: AdminRole,
    ) -> BetaCohort:
        row = self._repo.get_cohort_by_key(request.cohort_key)
        before = _cohort_state(row) if row else None
        if row is None:
            row = BetaCohort(
                cohort_id=_new_id("beta_cohort"),
                cohort_key=request.cohort_key,
                name=request.name,
                status=request.status.value,
                starts_at=request.starts_at,
                ends_at=request.ends_at,
                feature_flags=deepcopy(request.feature_flags),
                configuration=deepcopy(request.configuration),
                created_at=self._clock(),
                updated_at=self._clock(),
            )
            self._repo.add(row)
        else:
            row.name = request.name
            row.status = request.status.value
            row.starts_at = request.starts_at
            row.ends_at = request.ends_at
            row.feature_flags = deepcopy(request.feature_flags)
            row.configuration = deepcopy(request.configuration)
            row.updated_at = self._clock()
        self._repo.flush()
        self._admin_events.record_event(
            AdminEventLogInput(
                actor=actor_user_id,
                role=role,
                action="admin.beta_cohort.upserted",
                object_type="beta_cohort",
                object_id=row.cohort_key,
                before_state=before,
                after_state=_cohort_state(row),
                reason="upsert beta cohort configuration",
            )
        )
        return row

    def assign_cohort_membership(
        self,
        request: CohortMembershipCreate,
        *,
        actor_user_id: str,
        role: AdminRole,
    ) -> BetaCohortMembership:
        self._ensure_user(request.user_id)
        cohort = self._repo.get_cohort_by_key(request.cohort_key)
        if cohort is None:
            raise ProductMeasurementNotFound(request.cohort_key)
        row = self._repo.get_membership(user_id=request.user_id, cohort_id=cohort.cohort_id)
        before = _membership_state(row, cohort.cohort_key) if row else None
        if row is None:
            row = BetaCohortMembership(
                membership_id=_new_id("beta_member"),
                user_id=request.user_id,
                cohort_id=cohort.cohort_id,
                status=request.status.value,
                assigned_by=actor_user_id,
                starts_at=request.starts_at,
                ends_at=request.ends_at,
                configuration=deepcopy(request.configuration),
                created_at=self._clock(),
                updated_at=self._clock(),
            )
            self._repo.add(row)
        else:
            row.status = request.status.value
            row.starts_at = request.starts_at
            row.ends_at = request.ends_at
            row.configuration = deepcopy(request.configuration)
            row.updated_at = self._clock()
        self._repo.flush()
        self._admin_events.record_event(
            AdminEventLogInput(
                actor=actor_user_id,
                role=role,
                action="admin.beta_membership.assigned",
                object_type="beta_cohort_membership",
                object_id=row.membership_id,
                before_state=before,
                after_state=_membership_state(row, cohort.cohort_key),
                reason="assign beta cohort membership",
            )
        )
        return row

    def upsert_feature_gate(
        self,
        request: FeatureGateCreate,
        *,
        actor_user_id: str,
        role: AdminRole,
    ) -> ProductFeatureGate:
        row = self._repo.get_feature_gate(request.feature_key)
        before = _feature_gate_state(row) if row else None
        if row is None:
            row = ProductFeatureGate(
                feature_gate_id=_new_id("feature_gate"),
                feature_key=request.feature_key,
                enabled=request.enabled,
                access_mode=request.access_mode.value,
                cohort_keys=list(request.cohort_keys),
                entitlement_feature_key=request.entitlement_feature_key,
                configuration=deepcopy(request.configuration),
                created_at=self._clock(),
                updated_at=self._clock(),
            )
            self._repo.add(row)
        else:
            row.enabled = request.enabled
            row.access_mode = request.access_mode.value
            row.cohort_keys = list(request.cohort_keys)
            row.entitlement_feature_key = request.entitlement_feature_key
            row.configuration = deepcopy(request.configuration)
            row.updated_at = self._clock()
        self._repo.flush()
        self._admin_events.record_event(
            AdminEventLogInput(
                actor=actor_user_id,
                role=role,
                action="admin.feature_gate.upserted",
                object_type="product_feature_gate",
                object_id=row.feature_key,
                before_state=before,
                after_state=_feature_gate_state(row),
                reason="upsert product feature gate",
            )
        )
        return row

    def decide_feature_access(self, user_id: str, feature_key: str) -> FeatureAccessDecision:
        self._ensure_user(user_id)
        gate = self._repo.get_feature_gate(feature_key)
        active_memberships = self._active_memberships(user_id)
        cohort_keys = tuple(cohort.cohort_key for cohort, _membership in active_memberships)
        if gate is None:
            return FeatureAccessDecision(
                feature_key=feature_key,
                allowed=False,
                reason="feature gate is not configured",
                cohort_keys=cohort_keys,
            )
        if not gate.enabled:
            return FeatureAccessDecision(
                feature_key=feature_key,
                allowed=False,
                reason="feature gate is disabled",
                cohort_keys=cohort_keys,
                access_mode=FeatureAccessMode(gate.access_mode),
            )
        mode = FeatureAccessMode(gate.access_mode)
        if mode is FeatureAccessMode.OPEN:
            return _feature_decision(gate, True, "feature is open", cohort_keys)
        if mode is FeatureAccessMode.CLOSED:
            return _feature_decision(gate, False, "feature is closed", cohort_keys)
        allowed_by_cohort = bool(set(cohort_keys) & set(gate.cohort_keys or []))
        if mode is FeatureAccessMode.BETA_ONLY:
            return _feature_decision(
                gate,
                allowed_by_cohort,
                "active beta cohort membership allows feature"
                if allowed_by_cohort
                else "active beta cohort membership is required",
                cohort_keys,
            )
        entitlement_feature_key = gate.entitlement_feature_key or feature_key
        grant = self._effective_entitlement_grant(user_id, entitlement_feature_key)
        if grant is not None:
            return _feature_decision(
                gate,
                True,
                "product entitlement grant allows feature",
                cohort_keys,
                entitlement_source=grant.source_type,
            )
        try:
            monetization = evaluate_account_access(
                MonetizationRepository(self._session),
                user_id=user_id,
                feature_key=entitlement_feature_key,
                now=self._clock(),
            )
        except ValueError:
            return _feature_decision(
                gate,
                False,
                "no active product entitlement grant or monetization feature matched",
                cohort_keys,
            )
        return _feature_decision(
            gate,
            monetization.allowed,
            monetization.reason,
            cohort_keys,
            entitlement_source="monetization_plan" if monetization.allowed else None,
        )

    def assign_experiment(
        self,
        request: ExperimentAssignmentCreate,
        *,
        actor_user_id: str,
        role: AdminRole,
    ) -> ExperimentAssignment:
        self._ensure_user(request.user_id)
        cohort = self._repo.get_cohort_by_key(request.cohort_key) if request.cohort_key else None
        row = self._repo.get_assignment(
            user_id=request.user_id,
            experiment_key=request.experiment_key,
        )
        before = _assignment_state(row, request.cohort_key) if row else None
        if row is None:
            row = ExperimentAssignment(
                assignment_id=_new_id("experiment"),
                user_id=request.user_id,
                cohort_id=cohort.cohort_id if cohort else None,
                experiment_key=request.experiment_key,
                variant_key=request.variant_key,
                status="assigned",
                assignment_basis=request.assignment_basis,
                assigned_at=self._clock(),
                expires_at=request.expires_at,
                created_at=self._clock(),
                updated_at=self._clock(),
            )
            self._repo.add(row)
        else:
            row.cohort_id = cohort.cohort_id if cohort else None
            row.variant_key = request.variant_key
            row.status = "assigned"
            row.assignment_basis = request.assignment_basis
            row.expires_at = request.expires_at
            row.updated_at = self._clock()
        self._repo.flush()
        self._admin_events.record_event(
            AdminEventLogInput(
                actor=actor_user_id,
                role=role,
                action="admin.experiment_assignment.upserted",
                object_type="experiment_assignment",
                object_id=row.assignment_id,
                before_state=before,
                after_state=_assignment_state(row, request.cohort_key),
                reason="assign experiment variant",
            )
        )
        return row

    def create_entitlement_grant(
        self,
        request: EntitlementGrantCreate,
        *,
        actor_user_id: str,
        role: AdminRole,
    ) -> ProductEntitlementGrant:
        self._ensure_user(request.user_id)
        row = ProductEntitlementGrant(
            entitlement_grant_id=_new_id("entitlement"),
            user_id=request.user_id,
            feature_key=request.feature_key,
            source_type=request.source_type.value,
            source_ref_id=request.source_ref_id,
            status="active",
            effective_at=request.effective_at or self._clock(),
            expires_at=request.expires_at,
            reason=request.reason,
            created_at=self._clock(),
            updated_at=self._clock(),
        )
        self._repo.add(row)
        self._repo.flush()
        self._admin_events.record_event(
            AdminEventLogInput(
                actor=actor_user_id,
                role=role,
                action="admin.product_entitlement.granted",
                object_type="product_entitlement_grant",
                object_id=row.entitlement_grant_id,
                after_state=entitlement_grant_view(row).model_dump(mode="json"),
                reason=request.reason,
            )
        )
        return row

    def record_commercial_signal(
        self,
        user_id: str | None,
        request: CommercialExperimentSignalCreate,
    ) -> CommercialExperimentSignal:
        if user_id is not None:
            self._ensure_user(user_id)
        row = CommercialExperimentSignal(
            signal_id=_new_id("commercial_signal"),
            user_id=user_id,
            experiment_key=request.experiment_key,
            variant_key=request.variant_key,
            offer_key=request.offer_key.value,
            signal_type=request.signal_type.value,
            product_surface=request.product_surface,
            conversion_ref=request.conversion_ref,
            qualitative_feedback=request.qualitative_feedback,
            metadata_json=deepcopy(request.metadata),
            created_at=self._clock(),
            updated_at=self._clock(),
        )
        self._repo.add(row)
        self._repo.flush()
        event_type = (
            ProductEventType.COMMERCIAL_OFFER_EXPOSED
            if request.signal_type is CommercialSignalType.EXPOSED
            else ProductEventType.COMMERCIAL_CONVERSION_RECORDED
            if request.signal_type is CommercialSignalType.CONVERTED
            else ProductEventType.COMMERCIAL_OFFER_INTEREST_RECORDED
        )
        self.record_event(
            user_id,
            ProductEventCreate(
                event_type=event_type,
                event_source=ProductEventSource.FRONTEND,
                product_surface=request.product_surface,
                experiment_key=request.experiment_key,
                variant_key=request.variant_key,
                payload={
                    "offer_key": request.offer_key.value,
                    "signal_type": request.signal_type.value,
                    "conversion_present": request.conversion_ref is not None,
                },
            ),
        )
        return row

    def beta_access_summary(self, user_id: str) -> dict:
        memberships = self._active_memberships(user_id)
        return {
            "cohorts": [
                {
                    "cohort_key": cohort.cohort_key,
                    "name": cohort.name,
                    "status": cohort.status,
                    "membership_status": membership.status,
                    "configuration": membership.configuration,
                }
                for cohort, membership in memberships
            ],
            "feature_gates": [
                feature_gate_view(gate).model_dump(mode="json")
                for gate in self._repo.list_feature_gates()
            ],
        }

    def has_active_beta_access(self, user_id: str) -> bool:
        """Use the existing Layer 40 cohort authority for the production beta gate."""

        self._ensure_user(user_id)
        return bool(self._active_memberships(user_id))

    def list_cohorts(self) -> list[BetaCohort]:
        return self._repo.list_cohorts()

    def list_feature_gates(self) -> list[ProductFeatureGate]:
        return self._repo.list_feature_gates()

    def list_experiment_assignments(
        self,
        *,
        user_id: str | None = None,
        experiment_key: str | None = None,
    ) -> list[ExperimentAssignment]:
        return self._repo.list_assignments(user_id=user_id, experiment_key=experiment_key)

    def beta_analytics_summary(
        self,
        *,
        cohort_key: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> BetaAnalyticsSummary:
        events = self._repo.list_events(
            cohort_key=cohort_key,
            since=since,
            until=until,
            limit=10000,
        )
        stage_views: list[FunnelStageCount] = []
        previous_user_count: int | None = None
        for stage, event_types in FUNNEL_STAGES:
            type_values = {event_type.value for event_type in event_types}
            matching = [event for event in events if event.event_type in type_values]
            users = {event.user_id for event in matching if event.user_id is not None}
            conversion = (
                None if previous_user_count in {None, 0} else len(users) / previous_user_count
            )
            stage_views.append(
                FunnelStageCount(
                    stage=stage,
                    user_count=len(users),
                    event_count=len(matching),
                    conversion_from_previous=conversion,
                )
            )
            previous_user_count = len(users)

        feedback_rows = self._repo.list_recommendation_feedback(limit=10000)
        if cohort_key is not None:
            feedback_rows = [row for row in feedback_rows if row.cohort_key == cohort_key]
        support_rows = self._repo.list_support_cases(limit=10000)
        commercial_rows = self._repo.list_commercial_signals(limit=10000)
        trust_event_types = {
            ProductEventType.COVERAGE_LIMITATION_VIEWED.value,
            ProductEventType.TRUST_EXPLANATION_VIEWED.value,
        }
        return BetaAnalyticsSummary(
            generated_at=self._clock(),
            cohort_key=cohort_key,
            funnel=tuple(stage_views),
            recommendation_feedback={
                "total": len(feedback_rows),
                "useful": sum(1 for row in feedback_rows if row.useful),
                "not_useful": sum(1 for row in feedback_rows if not row.useful),
                "surprising": sum(1 for row in feedback_rows if row.surprising),
                "changed_decision": sum(1 for row in feedback_rows if row.changed_decision),
                "missing_alternative": sum(1 for row in feedback_rows if row.missing_alternative),
            },
            support_cases=dict(Counter(row.case_type for row in support_rows)),
            commercial_signals=dict(Counter(row.signal_type for row in commercial_rows)),
            trust_exposures=dict(
                Counter(
                    event.event_type for event in events if event.event_type in trust_event_types
                )
            ),
            causal_limitation=CAUSAL_LIMITATION,
        )

    def _validate_event_ownership(
        self,
        user_id: str | None,
        request: ProductEventCreate,
    ) -> None:
        if user_id is None:
            return
        if request.decision_id is not None:
            self._owned_decision(user_id, request.decision_id)
        if request.recommendation_id is not None:
            self._owned_recommendation(user_id, request.recommendation_id)
        if request.action_id is not None:
            self._owned_action(user_id, request.action_id)
        if request.application_id is not None:
            self._owned_application(user_id, request.application_id)
        if request.outcome_id is not None:
            self._owned_outcome(user_id, request.outcome_id)
        if request.career_identity_id is not None:
            identity = self._session.get(CareerIdentity, request.career_identity_id)
            if identity is None:
                raise ProductMeasurementNotFound(request.career_identity_id)
            if identity.user_id != user_id:
                raise CrossUserAccessBlocked(user_id, identity.user_id)

    def _validate_support_links(self, user_id: str, request: SupportCaseCreate) -> None:
        if request.decision_id is not None:
            self._owned_decision(user_id, request.decision_id)
        if request.recommendation_id is not None:
            self._owned_recommendation(user_id, request.recommendation_id)

    def _ensure_user(self, user_id: str) -> User:
        user = self._session.get(User, user_id)
        if user is None:
            raise UserNotFound(user_id)
        return user

    def _owned_decision(self, user_id: str, decision_id: str) -> CareerDecision:
        row = self._session.get(CareerDecision, decision_id)
        if row is None:
            raise ProductMeasurementNotFound(decision_id)
        if row.user_id != user_id:
            raise CrossUserAccessBlocked(user_id, row.user_id)
        return row

    def _owned_recommendation(self, user_id: str, recommendation_id: str) -> DecisionRecommendation:
        row = self._session.get(DecisionRecommendation, recommendation_id)
        if row is None:
            raise ProductMeasurementNotFound(recommendation_id)
        if row.user_id != user_id:
            raise CrossUserAccessBlocked(user_id, row.user_id)
        return row

    def _owned_action(self, user_id: str, action_id: str) -> CareerAction:
        row = self._session.get(CareerAction, action_id)
        if row is None:
            raise ProductMeasurementNotFound(action_id)
        if row.user_id != user_id:
            raise CrossUserAccessBlocked(user_id, row.user_id)
        return row

    def _owned_application(self, user_id: str, application_id: str) -> CareerApplication:
        row = self._session.get(CareerApplication, application_id)
        if row is None:
            raise ProductMeasurementNotFound(application_id)
        if row.user_id != user_id:
            raise CrossUserAccessBlocked(user_id, row.user_id)
        return row

    def _owned_outcome(self, user_id: str, outcome_id: str) -> CareerOutcome:
        row = self._session.get(CareerOutcome, outcome_id)
        if row is None:
            raise ProductMeasurementNotFound(outcome_id)
        if row.user_id != user_id:
            raise CrossUserAccessBlocked(user_id, row.user_id)
        return row

    def _active_memberships(self, user_id: str) -> list[tuple[BetaCohort, BetaCohortMembership]]:
        now = self._clock()
        result: list[tuple[BetaCohort, BetaCohortMembership]] = []
        for membership in self._repo.list_memberships(user_id=user_id, active_only=True):
            cohort = self._session.get(BetaCohort, membership.cohort_id)
            if cohort is None or cohort.status != CohortStatus.ACTIVE.value:
                continue
            if membership.starts_at is not None and _aware(membership.starts_at) > now:
                continue
            if membership.ends_at is not None and _aware(membership.ends_at) <= now:
                continue
            result.append((cohort, membership))
        return result

    def _effective_entitlement_grant(
        self,
        user_id: str,
        feature_key: str,
    ) -> ProductEntitlementGrant | None:
        now = self._clock()
        for grant in self._repo.list_entitlement_grants(user_id=user_id, feature_key=feature_key):
            if _aware(grant.effective_at) <= now and (
                grant.expires_at is None or _aware(grant.expires_at) > now
            ):
                return grant
        return None

    def _add_support_event(
        self,
        case: SupportCase,
        *,
        actor_user_id: str | None,
        event_type: str,
        before_state: dict | None = None,
        after_state: dict | None = None,
        note: str | None = None,
    ) -> SupportCaseEvent:
        row = SupportCaseEvent(
            support_case_event_id=_new_id("support_case_event"),
            support_case_id=case.support_case_id,
            actor_user_id=actor_user_id,
            event_type=event_type,
            before_state=deepcopy(before_state),
            after_state=deepcopy(after_state or _support_case_state(case)),
            note=note,
            created_at=self._clock(),
        )
        self._repo.add(row)
        self._repo.flush()
        return row


def product_event_view(row: ProductAnalyticsEvent) -> ProductEventView:
    return ProductEventView(
        event_id=row.event_id,
        user_id=row.user_id,
        event_type=ProductEventType(row.event_type),
        event_source=ProductEventSource(row.event_source),
        schema_version=row.schema_version,
        occurred_at=_aware(row.occurred_at),
        anonymous_session_id=row.anonymous_session_id,
        product_surface=row.product_surface,
        decision_id=row.decision_id,
        recommendation_id=row.recommendation_id,
        current_opportunity_id=row.current_opportunity_id,
        action_id=row.action_id,
        application_id=row.application_id,
        outcome_id=row.outcome_id,
        career_identity_id=row.career_identity_id,
        career_identity_version=row.career_identity_version,
        cohort_key=row.cohort_key,
        experiment_key=row.experiment_key,
        variant_key=row.variant_key,
        confidence_bucket=row.confidence_bucket,
        coverage_status=row.coverage_status,
        recommendation_state=row.recommendation_state,
        payload=row.payload or {},
        created_at=_aware(row.created_at),
    )


def recommendation_feedback_view(row: RecommendationFeedback) -> RecommendationFeedbackView:
    return RecommendationFeedbackView(
        feedback_id=row.feedback_id,
        user_id=row.user_id,
        decision_id=row.decision_id,
        recommendation_id=row.recommendation_id,
        useful=row.useful,
        surprising=row.surprising,
        changed_decision=row.changed_decision,
        missing_alternative=row.missing_alternative,
        missing_alternative_category=row.missing_alternative_category,
        confidence_calibration=row.confidence_calibration,
        feedback_comment=row.feedback_comment,
        cohort_key=row.cohort_key,
        experiment_key=row.experiment_key,
        variant_key=row.variant_key,
        created_at=_aware(row.created_at),
        updated_at=_aware(row.updated_at),
    )


def decision_reflection_view(row: DecisionReflection) -> DecisionReflectionView:
    return DecisionReflectionView(
        reflection_id=row.reflection_id,
        user_id=row.user_id,
        decision_id=row.decision_id,
        recommendation_id=row.recommendation_id,
        outcome_id=row.outcome_id,
        would_make_same_decision=row.would_make_same_decision,
        view_changed=row.view_changed,
        satisfaction_rating=row.satisfaction_rating,
        regret_level=row.regret_level,
        reflection_comment=row.reflection_comment,
        created_at=_aware(row.created_at),
        updated_at=_aware(row.updated_at),
    )


def strategy_change_view(row: StrategyChange) -> StrategyChangeView:
    return StrategyChangeView(
        strategy_change_id=row.strategy_change_id,
        user_id=row.user_id,
        decision_id=row.decision_id,
        recommendation_id=row.recommendation_id,
        change_type=row.change_type,
        previous_state=row.previous_state,
        new_state=row.new_state,
        reason_category=row.reason_category,
        occurred_at=_aware(row.occurred_at),
        note=row.note,
        created_at=_aware(row.created_at),
        updated_at=_aware(row.updated_at),
    )


def cohort_view(row: BetaCohort) -> CohortView:
    return CohortView(
        cohort_id=row.cohort_id,
        cohort_key=row.cohort_key,
        name=row.name,
        status=row.status,
        starts_at=_aware(row.starts_at),
        ends_at=_aware(row.ends_at),
        feature_flags=row.feature_flags or {},
        configuration=row.configuration or {},
        created_at=_aware(row.created_at),
        updated_at=_aware(row.updated_at),
    )


def membership_view(
    row: BetaCohortMembership,
    *,
    cohort_key: str,
) -> CohortMembershipView:
    return CohortMembershipView(
        membership_id=row.membership_id,
        user_id=row.user_id,
        cohort_id=row.cohort_id,
        cohort_key=cohort_key,
        status=CohortMembershipStatus(row.status),
        assigned_by=row.assigned_by,
        starts_at=_aware(row.starts_at),
        ends_at=_aware(row.ends_at),
        configuration=row.configuration or {},
        created_at=_aware(row.created_at),
        updated_at=_aware(row.updated_at),
    )


def feature_gate_view(row: ProductFeatureGate) -> FeatureGateView:
    return FeatureGateView(
        feature_gate_id=row.feature_gate_id,
        feature_key=row.feature_key,
        enabled=row.enabled,
        access_mode=row.access_mode,
        cohort_keys=tuple(row.cohort_keys or ()),
        entitlement_feature_key=row.entitlement_feature_key,
        configuration=row.configuration or {},
        created_at=_aware(row.created_at),
        updated_at=_aware(row.updated_at),
    )


def experiment_assignment_view(
    row: ExperimentAssignment,
    *,
    cohort_key: str | None = None,
) -> ExperimentAssignmentView:
    return ExperimentAssignmentView(
        assignment_id=row.assignment_id,
        user_id=row.user_id,
        experiment_key=row.experiment_key,
        variant_key=row.variant_key,
        cohort_key=cohort_key,
        assignment_basis=row.assignment_basis,
        expires_at=_aware(row.expires_at),
        status=row.status,
        assigned_at=_aware(row.assigned_at),
        created_at=_aware(row.created_at),
        updated_at=_aware(row.updated_at),
    )


def support_case_view(row: SupportCase) -> SupportCaseView:
    return SupportCaseView(
        support_case_id=row.support_case_id,
        user_id=row.user_id,
        case_type=row.case_type,
        status=row.status,
        title=row.title,
        description=row.description,
        subject_type=row.subject_type,
        subject_id=row.subject_id,
        decision_id=row.decision_id,
        recommendation_id=row.recommendation_id,
        current_opportunity_id=row.current_opportunity_id,
        privacy_request_type=row.privacy_request_type,
        priority=row.priority,
        assigned_operator_id=row.assigned_operator_id,
        resolution=row.resolution,
        resolved_at=_aware(row.resolved_at),
        closed_at=_aware(row.closed_at),
        created_at=_aware(row.created_at),
        updated_at=_aware(row.updated_at),
    )


def entitlement_grant_view(row: ProductEntitlementGrant) -> EntitlementGrantView:
    return EntitlementGrantView(
        entitlement_grant_id=row.entitlement_grant_id,
        user_id=row.user_id,
        feature_key=row.feature_key,
        source_type=row.source_type,
        source_ref_id=row.source_ref_id,
        status=row.status,
        effective_at=_aware(row.effective_at),
        expires_at=_aware(row.expires_at),
        reason=row.reason,
        created_at=_aware(row.created_at),
        updated_at=_aware(row.updated_at),
    )


def commercial_signal_view(row: CommercialExperimentSignal) -> CommercialExperimentSignalView:
    return CommercialExperimentSignalView(
        signal_id=row.signal_id,
        user_id=row.user_id,
        experiment_key=row.experiment_key,
        variant_key=row.variant_key,
        offer_key=row.offer_key,
        signal_type=row.signal_type,
        product_surface=row.product_surface,
        conversion_ref=row.conversion_ref,
        qualitative_feedback=row.qualitative_feedback,
        metadata=row.metadata_json or {},
        created_at=_aware(row.created_at),
        updated_at=_aware(row.updated_at),
    )


def _feature_decision(
    gate: ProductFeatureGate,
    allowed: bool,
    reason: str,
    cohort_keys: tuple[str, ...],
    *,
    entitlement_source: str | None = None,
) -> FeatureAccessDecision:
    return FeatureAccessDecision(
        feature_key=gate.feature_key,
        allowed=allowed,
        reason=reason,
        cohort_keys=cohort_keys,
        access_mode=FeatureAccessMode(gate.access_mode),
        entitlement_source=entitlement_source,
        configuration=gate.configuration or {},
    )


def _support_case_state(row: SupportCase) -> dict:
    return {
        "support_case_id": row.support_case_id,
        "user_id": row.user_id,
        "case_type": row.case_type,
        "status": row.status,
        "priority": row.priority,
        "assigned_operator_id": row.assigned_operator_id,
        "resolved_at": row.resolved_at.isoformat() if row.resolved_at else None,
        "closed_at": row.closed_at.isoformat() if row.closed_at else None,
    }


def _cohort_state(row: BetaCohort | None) -> dict | None:
    if row is None:
        return None
    return cohort_view(row).model_dump(mode="json")


def _membership_state(row: BetaCohortMembership | None, cohort_key: str) -> dict | None:
    if row is None:
        return None
    return membership_view(row, cohort_key=cohort_key).model_dump(mode="json")


def _feature_gate_state(row: ProductFeatureGate | None) -> dict | None:
    if row is None:
        return None
    return feature_gate_view(row).model_dump(mode="json")


def _assignment_state(row: ExperimentAssignment | None, cohort_key: str | None) -> dict | None:
    if row is None:
        return None
    return experiment_assignment_view(row, cohort_key=cohort_key).model_dump(mode="json")


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:24]}"
