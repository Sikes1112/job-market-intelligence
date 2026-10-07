from __future__ import annotations

import json
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

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
from backend.companies.models import Company
from backend.deep_decisions.models import (
    AdvisoryFinding,
    DecisionFactor,
    LongitudinalContextSnapshot,
    RecommendationEvolution,
    StrategicCareerReview,
)
from backend.geography.models import Region
from backend.ingestion.models import RawIngestionRecord
from backend.provenance.models import FactSourceLink, SourceObservation, SourceRef
from backend.scoring.models import RegionMarketScore
from backend.shared.confidence import Confidence
from backend.shared.provenance import (
    DataOrigin,
    LicenseTermsCategory,
    ObservationStatus,
    SourceType,
)
from backend.users.exceptions import CrossUserAccessBlocked
from backend.users.models import (
    ExternalAuthIdentity,
    User,
    UserPreferenceProfile,
    UserProfile,
)
from backend.users.repository import UserRepository
from backend.users.service import (
    PersonalizedRecommendationSnapshotInput,
    SavedMarketArtifactInput,
    UserPersonalizationPersistenceService,
    UserPreferenceProfileInput,
)

_NOW = datetime(2026, 5, 21, 15, tzinfo=UTC)


def _service(session: Session) -> UserPersonalizationPersistenceService:
    return UserPersonalizationPersistenceService(UserRepository(session))


def _seed_user_account(session: Session, user_id: str) -> None:
    suffix = user_id[-1]
    session.add(
        User(
            user_id=user_id,
        )
    )
    session.flush()
    session.add_all(
        [
            ExternalAuthIdentity(
                external_identity_id=f"external_{user_id}",
                user_id=user_id,
                provider="auth0",
                issuer="https://jmi.us.auth0.com/",
                subject=f"auth0|{user_id}",
                email=f"person-{suffix}@example.com",
                email_verified=True,
                last_seen_at=_NOW,
            ),
            UserProfile(
                user_id=user_id,
                display_name=f"Person {suffix.upper()}",
                email=f"person-{suffix}@example.com",
                avatar_url=f"https://cdn.example.com/{user_id}.png",
            ),
        ]
    )
    session.flush()


def _seed_user_owned_data(session: Session, user_id: str) -> None:
    service = _service(session)
    service.upsert_preference_profile(
        user_id,
        UserPreferenceProfileInput(
            role_interests=[f"role_{user_id}"],
            industry_interests=["software"],
            preferred_regions=["greater_boston"],
            prestige_weighting="medium",
            career_stage="entry_level",
        ),
    )
    service.save_market_artifact(
        user_id,
        SavedMarketArtifactInput(
            artifact_type="region",
            artifact_ref="greater_boston",
            label=f"Boston for {user_id}",
            snapshot={
                "entity_id": "greater_boston",
                "entity_type": "region",
                "saved_from": "privacy_controls",
            },
        ),
    )
    if user_id == "user_a":
        service.save_market_artifact(
            user_id,
            SavedMarketArtifactInput(
                artifact_type="company",
                artifact_ref="comp_a",
                notes="review later",
                snapshot={
                    "entity_id": "comp_a",
                    "entity_type": "company",
                    "saved_from": "privacy_controls",
                },
            ),
        )
    service.create_recommendation_snapshot(
        user_id,
        PersonalizedRecommendationSnapshotInput(
            preference_profile_id=user_id,
            personalized_output={
                "ranked_regions": [{"region_id": "greater_boston", "rank": 1}]
            },
            recommendation_version="personalized_rec_v1",
            source_version_bundle={"region_market_scores": {"greater_boston": 3}},
            objective_output_refs=[
                {"output_type": "region", "subject_id": "greater_boston"}
            ],
            recommendation_inputs_hash=f"sha256:{user_id}",
            generated_at=_NOW,
        ),
    )
    _seed_career_agent_memory_and_tool_data(session, user_id)
    _seed_career_identity_decision_and_deep_decision_data(session, user_id)


def _seed_career_agent_memory_and_tool_data(session: Session, user_id: str) -> None:
    suffix = user_id[-1]
    tool_id = f"agent_tool_{user_id}"
    session.add_all(
        [
            CareerMemoryPermissionRecord(
                career_memory_permission_id=f"mem_perm_{user_id}",
                user_id=user_id,
                category="career_constraints",
                enabled=True,
                personalize_allowed=True,
                visibility="private",
            ),
            CareerMemoryEntryRecord(
                career_memory_entry_id=f"mem_entry_{user_id}",
                user_id=user_id,
                category="career_constraints",
                value=f"Hybrid only {suffix}",
                label=f"Work preference {suffix}",
                notes=f"Personal note {suffix}",
                visibility="private",
                source="user_provided",
            ),
            CareerMemoryEntryRecord(
                career_memory_entry_id=f"mem_secret_{user_id}",
                user_id=user_id,
                category="career_constraints",
                value="Bearer closeout-secret-token",
                visibility="private",
                source="user_provided",
            ),
            CareerAgentToolRecord(
                career_agent_tool_id=tool_id,
                user_id=user_id,
                tool_type="reminder",
                status="awaiting_user_approval",
                action_boundary="reminder_creation",
                privacy_classification="user_private",
                approval_required=True,
                explicit_user_approval_required=True,
                approval_reason=f"User approval required {suffix}",
                proposed_action_summary=f"Create reminder for user {suffix}",
                preview_payload={
                    "title": f"Follow up {suffix}",
                    "authorization": "Bearer closeout-secret-token",
                },
                evidence_refs=[],
                freshness={"freshness_status": "fresh"},
                uncertainty={"confidence_level": "medium"},
                warnings=[],
                runtime_execution_performed=False,
            ),
        ]
    )
    session.flush()
    session.add(
        CareerAgentToolAuditEventRecord(
            career_agent_tool_audit_event_id=f"agent_tool_audit_{user_id}",
            career_agent_tool_id=tool_id,
            user_id=user_id,
            event_type="preview_created",
            summary=f"Career-agent tool preview created for {suffix}.",
        )
    )
    session.flush()


def _seed_career_identity_decision_and_deep_decision_data(
    session: Session,
    user_id: str,
) -> None:
    suffix = user_id[-1]
    identity_id = f"identity_{user_id}"
    fact_id = f"fact_{user_id}"
    import_id = f"import_{user_id}"
    decision_id = f"decision_{user_id}"
    context_id = f"context_{user_id}"
    option_id = f"option_{user_id}"
    recommendation_id = f"recommendation_{user_id}"
    version_id = f"version_{user_id}"
    plan_id = f"plan_{user_id}"
    action_id = f"action_{user_id}"
    application_id = f"application_{user_id}"
    transition_id = f"transition_{user_id}"
    outcome_id = f"outcome_{user_id}"
    factor_id = f"factor_{user_id}"
    longitudinal_context_id = f"longitudinal_{user_id}"
    evolution_id = f"evolution_{user_id}"
    finding_id = f"finding_{user_id}"
    review_id = f"review_{user_id}"

    session.add(
        CareerIdentity(
            career_identity_id=identity_id,
            user_id=user_id,
            current_version=1,
            completeness_state="complete",
            sufficiency_state="sufficient",
            ingestion_consent_granted=True,
            inference_consent_granted=True,
            downstream_personalization_consent_granted=True,
            completeness_snapshot={"role": "product"},
        )
    )
    session.add(
        CareerIdentityImport(
            career_identity_import_id=import_id,
            career_identity_id=identity_id,
            user_id=user_id,
            source_type="resume",
            source_label=f"resume-{suffix}.pdf",
            content_hash=f"sha256:{user_id}",
            artifact_metadata={"filename": f"resume-{suffix}.pdf"},
            import_status="completed",
            diagnostics=[],
            imported_fact_count=1,
        )
    )
    session.flush()
    session.add(
        CareerIdentityFact(
            career_identity_fact_id=fact_id,
            career_identity_id=identity_id,
            user_id=user_id,
            fact_type="role_preference",
            normalized_key=f"role:{suffix}",
            state="confirmed",
            payload={"role_title": f"Product Lead {suffix}"},
            provenance={"source": import_id},
            source_import_id=import_id,
            source_label=f"resume-{suffix}.pdf",
        )
    )
    session.flush()

    decision = CareerDecision(
        decision_id=decision_id,
        user_id=user_id,
        career_identity_id=identity_id,
        decision_type="career_path",
        status="evaluating",
        title=f"Choose path {suffix}",
        description=f"Decision notes {suffix}",
        priorities=[{"key": "growth", "weight": 5}],
        constraints=[{"key": "minimum_compensation", "value": 100000}],
    )
    session.add(decision)
    session.flush()
    session.add_all(
        [
            DecisionContextSnapshot(
                context_snapshot_id=context_id,
                user_id=user_id,
                career_identity_id=identity_id,
                career_identity_version=1,
                completeness_state="complete",
                sufficiency_state="sufficient",
                context_payload={"role_preferences": [f"Product Lead {suffix}"]},
                fact_refs=[fact_id],
            ),
            DecisionOption(
                option_id=option_id,
                user_id=user_id,
                decision_id=decision_id,
                title=f"Option {suffix}",
                scenario={"region_ids": ["greater_boston"], "company_ids": ["comp_a"]},
                status="active",
                position=0,
            ),
        ]
    )
    session.flush()
    session.add(
        DecisionRecommendation(
            recommendation_id=recommendation_id,
            user_id=user_id,
            decision_id=decision_id,
            context_snapshot_id=context_id,
            recommended_option_id=option_id,
            recommendation_status="ready",
            evidence_sufficiency="comparison_ready",
            confidence="medium",
            summary=f"Recommended option {suffix}",
            fit_payload={"fit": "strong"},
            comparison_payload={"ranked_options": [option_id]},
            evidence_payload={"facts": [fact_id]},
            challenge_payload=[],
            limitations=[],
        )
    )
    session.flush()
    decision.current_context_snapshot_id = context_id
    decision.current_recommendation_id = recommendation_id
    decision.selected_option_id = option_id
    session.add_all(
        [
            DecisionVersion(
                decision_version_id=version_id,
                user_id=user_id,
                decision_id=decision_id,
                version_number=1,
                version_reason="created",
                decision_snapshot={"title": decision.title},
                options_snapshot=[{"option_id": option_id}],
                recommendation_snapshot={"recommendation_id": recommendation_id},
                selected_option_id=option_id,
                context_snapshot_id=context_id,
                user_note=f"Journal {suffix}",
            ),
            CareerActionPlan(
                action_plan_id=plan_id,
                user_id=user_id,
                decision_id=decision_id,
                selected_option_id=option_id,
                title=f"Plan {suffix}",
                plan_payload={"steps": ["research"]},
            ),
        ]
    )
    session.flush()
    session.add(
        CareerAction(
            action_id=action_id,
            user_id=user_id,
            action_plan_id=plan_id,
            decision_id=decision_id,
            option_id=option_id,
            action_type="research",
            status="open",
            title=f"Action {suffix}",
            metadata_json={"private_note": suffix},
        )
    )
    session.flush()
    session.add(
        CareerApplication(
            application_id=application_id,
            user_id=user_id,
            decision_id=decision_id,
            action_id=action_id,
            option_id=option_id,
            company_id="comp_a",
            region_id="greater_boston",
            role_title=f"Product Lead {suffix}",
            status="applied",
            notes=f"Application note {suffix}",
        )
    )
    session.flush()
    session.add_all(
        [
            CareerApplicationTransition(
                transition_id=transition_id,
                user_id=user_id,
                application_id=application_id,
                from_status="considering",
                to_status="applied",
                reason=f"Submitted {suffix}",
            ),
            CareerOutcome(
                outcome_id=outcome_id,
                user_id=user_id,
                decision_id=decision_id,
                action_id=action_id,
                application_id=application_id,
                option_id=option_id,
                recommendation_id=recommendation_id,
                outcome_type="application_progress",
                status="observed",
                title=f"Outcome {suffix}",
                reflection=f"Reflection {suffix}",
            ),
            DecisionFactor(
                factor_id=factor_id,
                user_id=user_id,
                decision_id=decision_id,
                option_id=option_id,
                recommendation_id=recommendation_id,
                context_snapshot_id=context_id,
                domain="fit",
                category="benefit",
                factor_key=f"factor_{suffix}",
                label=f"Factor {suffix}",
                direction="positive",
                importance=5,
                confidence="medium",
                uncertainty="bounded",
                evidence_strength="moderate",
                evidence_kind="derived",
                provenance={"source": "test"},
                explanation=f"Factor explanation {suffix}",
                caveats=[],
                freshness_status="fresh",
            ),
            LongitudinalContextSnapshot(
                longitudinal_context_id=longitudinal_context_id,
                user_id=user_id,
                decision_id=decision_id,
                window_start=_NOW,
                window_end=_NOW,
                record_count=1,
                context_payload={"decisions": [decision_id]},
                evidence_payload={"applications": [application_id]},
            ),
            RecommendationEvolution(
                evolution_id=evolution_id,
                user_id=user_id,
                decision_id=decision_id,
                current_recommendation_id=recommendation_id,
                change_type="none",
                meaningful_changes=[],
                confidence_after="medium",
                evidence_basis={"recommendation": recommendation_id},
                uncertainty="bounded",
                explanation=f"No change {suffix}",
            ),
            AdvisoryFinding(
                advisory_finding_id=finding_id,
                user_id=user_id,
                decision_id=decision_id,
                finding_type="risk",
                severity="watch",
                support_status="supported",
                confidence="medium",
                uncertainty="bounded",
                window_start=_NOW,
                window_end=_NOW,
                affected_goal=f"Goal {suffix}",
                supporting_evidence=[{"factor_id": factor_id}],
                counter_evidence=[],
                explanation=f"Finding {suffix}",
            ),
        ]
    )
    session.flush()
    session.add(
        StrategicCareerReview(
            strategic_review_id=review_id,
            user_id=user_id,
            decision_id=decision_id,
            longitudinal_context_id=longitudinal_context_id,
            status="generated",
            window_start=_NOW,
            window_end=_NOW,
            goals={"primary": f"Goal {suffix}"},
            strategy_performance={"status": "steady"},
            application_summary={"applications": 1},
            outcome_summary={"outcomes": 1},
            identity_changes=[],
            market_changes=[],
            recommendation_changes=[],
            active_risks=[],
            blind_spots=[],
            suggested_next_actions=[],
            confidence="medium",
            uncertainty="bounded",
        )
    )
    session.flush()


def _seed_users_and_personalization(session: Session) -> None:
    for user_id in ("user_a", "user_b"):
        _seed_user_account(session, user_id)
        _seed_user_owned_data(session, user_id)


def _seed_market_rows(session: Session) -> None:
    session.add_all(
        [
            Region(
                region_id="greater_boston",
                region_name="greater_boston",
                display_name="Greater Boston",
                region_type="greater_region",
            ),
            Company(
                company_id="comp_a",
                company_name="A",
                normalized_company_name="a",
                eligibility_status="eligible",
            ),
            SourceRef(
                source_id="source_a",
                source_type=SourceType.COMPANY_OFFICIAL.value,
                source_name="Example Careers",
                url_or_provider="https://example.test/careers",
                collected_at=_NOW,
                observed_at=_NOW,
                license_or_terms_category=LicenseTermsCategory.PUBLIC.value,
                confidence=Confidence.HIGH.value,
                data_origin=DataOrigin.REAL_OBSERVED.value,
            ),
        ]
    )
    session.flush()
    session.add_all(
        [
            RegionMarketScore(
                region_score_id="score_boston",
                region_id="greater_boston",
                objective_opportunity_score=0.74,
                score_ruleset_version="marketscore_v1",
                source_version_bundle={"source_a": 4},
            ),
            SourceObservation(
                observation_id="obs_a",
                source_id="source_a",
                source_type=SourceType.COMPANY_OFFICIAL.value,
                source_name="Example Careers",
                url_or_provider="https://example.test/careers",
                collected_at=_NOW,
                observed_at=_NOW,
                license_or_terms_category=LicenseTermsCategory.PUBLIC.value,
                confidence=Confidence.HIGH.value,
                data_origin=DataOrigin.REAL_OBSERVED.value,
                observation_status=ObservationStatus.POSITIVE_OBSERVED.value,
            ),
        ]
    )
    session.flush()
    session.add_all(
        [
            FactSourceLink(
                link_id="link_score_boston",
                observation_id="obs_a",
                source_id="source_a",
                fact_type="region_score",
                fact_id="score_boston",
                fact_field="objective_opportunity_score",
                source_type=SourceType.COMPANY_OFFICIAL.value,
                source_name="Example Careers",
                url_or_provider="https://example.test/careers",
                collected_at=_NOW,
                observed_at=_NOW,
                license_or_terms_category=LicenseTermsCategory.PUBLIC.value,
                confidence=Confidence.HIGH.value,
                data_origin=DataOrigin.REAL_OBSERVED.value,
                observation_status=ObservationStatus.POSITIVE_OBSERVED.value,
            ),
            RawIngestionRecord(
                raw_record_id="raw_a",
                provider_id="manual",
                source_type=SourceType.COMPANY_OFFICIAL.value,
                source_name="Example Careers",
                url_or_provider="https://example.test/careers",
                external_entity_id="greater_boston",
                raw_payload={"objective_opportunity_score": 0.74},
                normalized_payload={"region_id": "greater_boston"},
                payload_checksum="checksum_a",
                schema_version="manual_v1",
                collected_at=_NOW,
                observed_at=_NOW,
                ingestion_status="stored",
                normalization_status="normalized",
                intended_fact_type="region_score",
                source_id="source_a",
                observation_id="obs_a",
            ),
        ]
    )
    session.flush()


def _market_state(session: Session) -> dict:
    region = session.get(Region, "greater_boston")
    company = session.get(Company, "comp_a")
    score = session.get(RegionMarketScore, "score_boston")
    source_ref = session.get(SourceRef, "source_a")
    observation = session.get(SourceObservation, "obs_a")
    link = session.get(FactSourceLink, "link_score_boston")
    raw = session.get(RawIngestionRecord, "raw_a")
    return {
        "region_version": region.version,
        "region_display_name": region.display_name,
        "company_version": company.version,
        "score_version": score.version,
        "score_value": score.objective_opportunity_score,
        "source_ref_version": source_ref.version,
        "source_ref_collected_at": source_ref.collected_at,
        "observation_version": observation.version,
        "observation_observed_at": observation.observed_at,
        "link_version": link.version,
        "raw_version": raw.version,
        "raw_payload": deepcopy(raw.raw_payload),
        "raw_status": raw.ingestion_status,
    }


def _assert_market_unchanged(session: Session, before: dict) -> None:
    assert _market_state(session) == before


def _seed_everything(session: Session) -> dict:
    _seed_market_rows(session)
    _seed_users_and_personalization(session)
    return _market_state(session)


def test_export_includes_current_user_owned_data_and_excludes_other_users(
    session: Session,
) -> None:
    before = _seed_everything(session)
    service = _service(session)

    exported = service.export_user_data("user_a")

    assert exported["export_schema_version"] == "layer7_privacy_export_v1"
    assert exported["user"]["user_id"] == "user_a"
    assert exported["profile"]["email"] == "person-a@example.com"
    assert exported["profile"]["created_at"] is not None
    assert exported["external_auth_identities"][0]["subject"] == "auth0|user_a"
    assert exported["preference_profile"]["role_interests"] == ["role_user_a"]
    assert exported["preference_profile"]["created_at"] is not None
    assert {row["artifact_ref"] for row in exported["saved_market_artifacts"]} == {
        "greater_boston",
        "comp_a",
    }
    snapshot = exported["personalized_recommendation_snapshots"][0]
    assert snapshot["recommendation_version"] == "personalized_rec_v1"
    assert snapshot["recommendation_inputs_hash"] == "sha256:user_a"
    assert snapshot["objective_output_refs"] == [
        {"output_type": "region", "subject_id": "greater_boston"}
    ]
    assert snapshot["generated_at"].startswith("2026-05-21T15:00:00")
    assert exported["career_identity"]["career_identity_id"] == "identity_user_a"
    assert exported["career_identity"]["facts"][0]["payload"] == {
        "role_title": "Product Lead a"
    }
    assert exported["career_identity"]["imports"][0]["source_label"] == "resume-a.pdf"
    assert exported["career_identity"]["raw_import_content_retained"] is False
    assert exported["career_decisions"]["decisions"][0]["decision_id"] == (
        "decision_user_a"
    )
    assert exported["career_decisions"]["versions"][0]["user_note"] == "Journal a"
    assert exported["career_decisions"]["applications"][0]["notes"] == (
        "Application note a"
    )
    assert exported["deep_decision_intelligence"]["factors"][0]["factor_id"] == (
        "factor_user_a"
    )
    assert exported["deep_decision_intelligence"]["strategic_reviews"][0]["goals"] == {
        "primary": "Goal a"
    }
    assert exported["career_agent_memory"]["permissions"][0]["category"] == (
        "career_constraints"
    )
    memory_entries = exported["career_agent_memory"]["entries"]
    assert {entry["value"] for entry in memory_entries} == {
        "Hybrid only a",
        "[REDACTED]",
    }
    assert exported["career_agent_tools"][0]["tool_request_id"] == "agent_tool_user_a"
    assert exported["career_agent_tools"][0]["proposed_action_summary"] == (
        "Create reminder for user a"
    )
    assert exported["career_agent_tools"][0]["user_visible_preview"] == {
        "title": "Follow up a",
        "authorization": "[REDACTED]",
    }
    assert "agent_tool_audit_user_a" not in json.dumps(exported, sort_keys=True)
    assert "closeout-secret-token" not in json.dumps(exported, sort_keys=True)
    assert "user_b" not in json.dumps(exported, sort_keys=True)

    with pytest.raises(CrossUserAccessBlocked):
        service.export_user_data("user_a", owner_user_id="user_b")
    _assert_market_unchanged(session, before)


def test_delete_preferences_removes_only_current_user_preferences(
    session: Session,
) -> None:
    before = _seed_everything(session)
    service = _service(session)

    deleted = service.delete_preference_profile("user_a")

    assert deleted == 1
    assert session.get(UserPreferenceProfile, "user_a") is None
    assert session.get(UserPreferenceProfile, "user_b") is not None
    snapshots = service.list_recommendation_snapshots("user_a")
    assert len(snapshots) == 1
    assert snapshots[0].preference_profile_id is None
    assert service.list_recommendation_snapshots("user_b")[0].preference_profile_id == (
        "user_b"
    )
    with pytest.raises(CrossUserAccessBlocked):
        service.delete_preference_profile("user_a", owner_user_id="user_b")
    _assert_market_unchanged(session, before)


def test_delete_saved_artifacts_removes_only_current_user_artifacts(
    session: Session,
) -> None:
    before = _seed_everything(session)
    service = _service(session)

    deleted = service.delete_saved_market_artifacts("user_a")

    assert deleted == 2
    assert service.list_saved_market_artifacts("user_a") == []
    assert len(service.list_saved_market_artifacts("user_b")) == 1
    with pytest.raises(CrossUserAccessBlocked):
        service.delete_saved_market_artifacts("user_a", owner_user_id="user_b")
    _assert_market_unchanged(session, before)


def test_delete_recommendation_snapshots_removes_only_current_user_snapshots(
    session: Session,
) -> None:
    before = _seed_everything(session)
    service = _service(session)

    deleted = service.delete_recommendation_snapshots("user_a")

    assert deleted == 1
    assert service.list_recommendation_snapshots("user_a") == []
    assert len(service.list_recommendation_snapshots("user_b")) == 1
    with pytest.raises(CrossUserAccessBlocked):
        service.delete_recommendation_snapshots("user_a", owner_user_id="user_b")
    _assert_market_unchanged(session, before)


def test_deactivate_account_removes_current_user_owned_layer7_data_only(
    session: Session,
) -> None:
    before = _seed_everything(session)
    service = _service(session)

    result = service.deactivate_user_account("user_a")

    assert result.user_id == "user_a"
    assert result.user_status == "deactivated"
    assert result.deleted_preference_profiles == 1
    assert result.deleted_saved_market_artifacts == 2
    assert result.deleted_recommendation_snapshots == 1
    assert result.deleted_career_identities == 1
    assert result.deleted_career_identity_facts == 1
    assert result.deleted_career_identity_imports == 1
    assert result.deleted_career_decision_records == 10
    assert result.deleted_deep_decision_records == 5
    assert result.deleted_profiles == 1
    assert result.deleted_external_auth_identities == 0
    assert result.scrubbed_external_auth_identities == 1
    assert session.get(User, "user_a").status == "deactivated"
    assert session.get(UserProfile, "user_a") is None
    retained_identity = UserRepository(session).list_external_identities("user_a")[0]
    assert retained_identity.email is None
    assert retained_identity.email_verified is None
    assert retained_identity.provider == "auth0"
    assert retained_identity.issuer == "https://jmi.us.auth0.com/"
    assert retained_identity.subject == "auth0|user_a"
    assert retained_identity.last_seen_at != _NOW
    assert session.query(CareerMemoryPermissionRecord).filter_by(user_id="user_a").all() == []
    assert session.query(CareerMemoryEntryRecord).filter_by(user_id="user_a").all() == []
    assert session.query(CareerAgentToolAuditEventRecord).filter_by(user_id="user_a").all() == []
    assert session.query(CareerAgentToolRecord).filter_by(user_id="user_a").all() == []
    assert session.get(UserPreferenceProfile, "user_a") is None
    assert session.get(CareerIdentity, "identity_user_a") is None
    assert session.get(CareerIdentityFact, "fact_user_a") is None
    assert session.get(CareerIdentityImport, "import_user_a") is None
    assert session.query(CareerDecision).filter_by(user_id="user_a").all() == []
    assert session.query(DecisionVersion).filter_by(user_id="user_a").all() == []
    assert session.query(CareerApplication).filter_by(user_id="user_a").all() == []
    assert session.query(CareerOutcome).filter_by(user_id="user_a").all() == []
    assert session.query(DecisionFactor).filter_by(user_id="user_a").all() == []
    assert session.query(StrategicCareerReview).filter_by(user_id="user_a").all() == []
    assert service.list_saved_market_artifacts("user_a") == []
    assert service.list_recommendation_snapshots("user_a") == []

    assert session.get(User, "user_b").status == "active"
    assert session.get(UserProfile, "user_b") is not None
    assert len(UserRepository(session).list_external_identities("user_b")) == 1
    assert session.get(UserPreferenceProfile, "user_b") is not None
    assert session.query(CareerMemoryPermissionRecord).filter_by(user_id="user_b").count() == 1
    assert session.query(CareerMemoryEntryRecord).filter_by(user_id="user_b").count() == 2
    assert session.query(CareerAgentToolRecord).filter_by(user_id="user_b").count() == 1
    assert session.get(CareerIdentity, "identity_user_b") is not None
    assert session.query(CareerDecision).filter_by(user_id="user_b").count() == 1
    assert session.query(DecisionFactor).filter_by(user_id="user_b").count() == 1
    assert session.query(StrategicCareerReview).filter_by(user_id="user_b").count() == 1
    assert len(service.list_saved_market_artifacts("user_b")) == 1
    assert len(service.list_recommendation_snapshots("user_b")) == 1
    with pytest.raises(CrossUserAccessBlocked):
        service.deactivate_user_account("user_a", owner_user_id="user_b")
    _assert_market_unchanged(session, before)


def test_privacy_docs_defer_auth0_provider_account_deletion() -> None:
    docs = Path("docs/AUTH_USER_FOUNDATION.md").read_text()
    normalized = " ".join(docs.split())

    assert "Auth0 provider account deletion is deferred" in docs
    assert "does not call Auth0 Management API" in normalized
    assert "public market exploration endpoints remain unauthenticated" in normalized
