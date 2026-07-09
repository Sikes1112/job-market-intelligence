from __future__ import annotations

import json
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.admin.roles import AdminRole
from backend.data_standards.models import DataStandardPartnerSubmissionRecord
from backend.data_standards.schemas import (
    DataQualityLabelValue,
    GovernanceArea,
    GovernanceStatus,
    PartnerRecordType,
    PartnerTrustTier,
    PartnerType,
    PartnerValidationStatus,
    PartnerVerificationStatus,
)
from backend.data_standards.service import (
    PARTNER_SCHEMA_VERSION,
    REQUIRED_FIELDS_BY_RECORD_TYPE,
    DataStandardsService,
)
from backend.users.models import User

REQUIRED_STANDARD_TERMS = {
    "entry_level_role",
    "internship",
    "co_op",
    "early_career_program",
    "company_region_presence",
    "hiring_activity",
    "market_opportunity_score",
}

CANONICAL_BOUNDARY_TABLES = (
    "companies",
    "regions",
    "company_region_presence",
    "company_region_hiring",
    "company_region_entry_level",
    "region_market_scores",
    "opportunities",
    "opportunity_sources",
    "opportunity_submissions",
    "market_snapshots",
    "company_region_snapshots",
    "sector_region_snapshots",
    "market_score_history",
    "historical_observations",
    "predictive_signals",
    "signal_inputs",
    "market_indices",
    "market_index_versions",
    "market_index_scores",
    "market_index_inputs",
    "benchmark_reports",
    "benchmark_report_sections",
    "benchmark_report_rankings",
    "benchmark_report_evidence",
    "data_contributions",
    "contribution_evidence",
    "contribution_reviews",
    "personalized_recommendation_snapshots",
    "career_memory_entries",
    "career_agent_tool_records",
)


def _valid_submission(
    submission_id: str = "sub_27a_valid",
    *,
    partner_id: str = "partner_acme_employer",
) -> dict[str, Any]:
    return {
        "submission_id": submission_id,
        "partner_id": partner_id,
        "submitted_at": "2026-06-30T12:00:00Z",
        "schema_version": PARTNER_SCHEMA_VERSION,
        "submitter_type": "employer",
        "records": [
            {
                "record_id": "rec_company_1",
                "record_type": "company",
                "payload": {
                    "company_name": "Acme AI",
                    "company_website": "https://acme.example",
                },
                "source_ref_ids": ["src_1"],
            },
            {
                "record_id": "rec_presence_1",
                "record_type": "company_region_presence",
                "payload": {
                    "company_name": "Acme AI",
                    "region_name": "Greater Boston",
                    "presence_status": "office_plus_hiring",
                    "observed_at": "2026-06-15",
                },
                "source_ref_ids": ["src_1"],
            },
        ],
        "source_refs": [
            {
                "source_ref_id": "src_1",
                "source_type": "employer_official",
                "url": "https://acme.example/careers",
                "collected_at": "2026-06-30T10:00:00Z",
                "license_or_terms_category": "partner_terms",
            }
        ],
        "freshness": {
            "freshness_status": "fresh",
            "observed_at": "2026-06-30T10:00:00Z",
            "freshness_expires_at": "2026-07-30T10:00:00Z",
        },
        "confidence": {
            "confidence_label": "high",
            "confidence_score": 0.88,
            "rationale": "Employer-submitted with official source.",
        },
        "warnings": [
            {
                "code": "partner_submitted",
                "message": "Partner-submitted data requires downstream review.",
            }
        ],
    }


def _auth_headers(subject: str) -> dict[str, str]:
    suffix = subject.split("|")[-1]
    claims = {
        "iss": "https://jmi.us.auth0.com/",
        "sub": subject,
        "email": f"{suffix}@example.com",
        "email_verified": True,
        "name": f"User {suffix}",
    }
    return {"X-Verified-OIDC-Claims": json.dumps(claims)}


def _assign_role(
    api_client: TestClient,
    session: Session,
    role: AdminRole | None,
    *,
    subject: str,
) -> dict[str, str]:
    headers = _auth_headers(subject)
    response = api_client.get("/me", headers=headers)
    assert response.status_code == 200
    user_id = response.json()["data"]["user"]["user_id"]
    user = session.get(User, user_id)
    assert user is not None
    user.admin_role = role.value if role is not None else None
    session.flush()
    return headers


def _quality_eval_payload(
    label: str,
    *,
    partner_id: str | None = "partner_state_university",
    source_type: str = "employer_official",
    confidence_label: str = "high",
    freshness_status: str = "fresh",
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "label": label,
        "source_refs": [
            {
                "source_ref_id": "src_eval_1",
                "source_type": source_type,
                "url": "https://example.edu/careers/source",
                "collected_at": "2026-06-30T10:00:00Z",
            }
        ],
        "freshness": {
            "freshness_status": freshness_status,
            "observed_at": "2026-06-30T10:00:00Z",
        },
        "confidence": {
            "confidence_label": confidence_label,
            "confidence_score": 0.91,
            "rationale": "Layer 27 test fixture with declared evidence.",
        },
    }
    if partner_id is not None:
        payload["partner_id"] = partner_id
    return payload


def _counts(session: Session, table_names: tuple[str, ...]) -> dict[str, int]:
    return {
        table_name: session.execute(
            text(f"select count(*) from {table_name}")
        ).scalar_one()
        for table_name in table_names
    }


def test_all_required_standard_definitions_exist_with_metadata() -> None:
    result = DataStandardsService().standard_definitions()

    definitions = {definition.canonical_name: definition for definition in result.definitions}
    assert REQUIRED_STANDARD_TERMS.issubset(definitions)

    for definition in definitions.values():
        assert definition.term
        assert definition.canonical_name
        assert definition.description
        assert definition.inclusion_criteria
        assert definition.exclusion_criteria
        assert definition.examples
        assert definition.version
        assert definition.status.value == "active"


def test_partner_schema_exposes_supported_record_types_and_required_fields() -> None:
    schema = DataStandardsService().partner_schema()

    assert schema.schema_version == PARTNER_SCHEMA_VERSION
    assert set(schema.supported_record_types) == {
        record_type.value for record_type in PartnerRecordType
    }
    assert schema.required_fields_by_record_type == REQUIRED_FIELDS_BY_RECORD_TYPE
    assert schema.freshness_required is True
    assert schema.confidence_required is True
    assert "validated" in schema.validation_statuses
    assert "accepted_as_candidate" in schema.review_lifecycle_states
    assert "records" in schema.required_submission_fields


def test_valid_partner_submission_passes_validation() -> None:
    result = DataStandardsService().validate_submission(_valid_submission())

    assert result.validation_status is PartnerValidationStatus.VALIDATED
    assert result.errors == ()
    assert result.normalized_submission is not None
    assert result.normalized_submission.validation_status is PartnerValidationStatus.VALIDATED


def test_invalid_partner_submission_is_rejected_with_structured_errors() -> None:
    payload = _valid_submission()
    payload.pop("partner_id")
    payload["schema_version"] = "unknown_version"
    payload["submitter_type"] = "unsupported_partner"
    payload["records"][0]["record_type"] = "unsupported_record"
    payload["records"][1]["payload"].pop("region_name")
    payload["records"][1]["source_ref_ids"] = ["missing_source"]
    payload["freshness"] = {}
    payload.pop("confidence")

    result = DataStandardsService().validate_submission(payload)

    assert result.validation_status is PartnerValidationStatus.REJECTED
    error_codes = {error.code for error in result.errors}
    assert {
        "required_field_missing",
        "unsupported_schema_version",
        "unsupported_submitter_type",
        "unsupported_record_type",
        "required_record_field_missing",
        "unknown_source_ref",
    }.issubset(error_codes)
    assert all(error.field and error.message for error in result.errors)


def test_source_freshness_confidence_and_warnings_survive_serialization(
    api_client: TestClient,
    session: Session,
) -> None:
    reviewer_headers = _assign_role(
        api_client,
        session,
        AdminRole.DATA_REVIEWER,
        subject="auth0|layer27_validation_reviewer",
    )
    response = api_client.post(
        "/data-standards/partner-submissions/validate",
        headers=reviewer_headers,
        json=_valid_submission(),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    submission = data["normalized_submission"]
    assert submission["source_refs"][0]["source_ref_id"] == "src_1"
    assert submission["freshness"]["freshness_status"] == "fresh"
    assert submission["confidence"]["confidence_label"] == "high"
    assert submission["warnings"][0]["code"] == "partner_submitted"


def test_partner_submission_creation_is_bounded_to_layer_27_table(
    session: Session,
) -> None:
    before = _counts(session, CANONICAL_BOUNDARY_TABLES)

    submission = DataStandardsService(session).create_submission(_valid_submission())
    session.commit()

    after = _counts(session, CANONICAL_BOUNDARY_TABLES)
    assert after == before
    assert submission.submission_id == "sub_27a_valid"
    rows = session.query(DataStandardPartnerSubmissionRecord).all()
    assert [row.partner_submission_id for row in rows] == ["sub_27a_valid"]
    assert rows[0].records_json[0]["payload"]["company_name"] == "Acme AI"


def test_partner_submission_creation_goes_through_validation(
    api_client: TestClient,
    session: Session,
) -> None:
    reviewer_headers = _assign_role(
        api_client,
        session,
        AdminRole.DATA_REVIEWER,
        subject="auth0|layer27_creation_reviewer",
    )
    payload = _valid_submission("sub_27a_invalid")
    payload["records"][0]["payload"].pop("company_website")

    response = api_client.post(
        "/data-standards/partner-submissions",
        headers=reviewer_headers,
        json=payload,
    )

    assert response.status_code == 400
    assert response.json()["data"]["validation_status"] == "rejected"
    assert session.query(DataStandardPartnerSubmissionRecord).count() == 0


def test_layer_27_routes_are_registered_and_reachable(
    api_client: TestClient,
    session: Session,
) -> None:
    ordinary_headers = _assign_role(
        api_client,
        session,
        None,
        subject="auth0|layer27_ordinary",
    )
    reviewer_headers = _assign_role(
        api_client,
        session,
        AdminRole.DATA_REVIEWER,
        subject="auth0|layer27_reviewer",
    )
    definitions = api_client.get("/data-standards/definitions")
    partner_schema = api_client.get("/data-standards/partner-schema")
    unauthenticated_validation = api_client.post(
        "/data-standards/partner-submissions/validate",
        json=_valid_submission(),
    )
    ordinary_creation = api_client.post(
        "/data-standards/partner-submissions",
        headers=ordinary_headers,
        json=_valid_submission("sub_27a_ordinary_denied"),
    )
    validation = api_client.post(
        "/data-standards/partner-submissions/validate",
        headers=reviewer_headers,
        json=_valid_submission(),
    )
    creation = api_client.post(
        "/data-standards/partner-submissions",
        headers=reviewer_headers,
        json=_valid_submission("sub_27a_api_create"),
    )

    assert definitions.status_code == 200
    assert partner_schema.status_code == 200
    assert unauthenticated_validation.status_code == 401
    assert ordinary_creation.status_code == 403
    assert validation.status_code == 200
    assert creation.status_code == 200
    assert definitions.json()["data"]["definitions"]
    assert partner_schema.json()["data"]["schema_version"] == PARTNER_SCHEMA_VERSION
    assert validation.json()["data"]["validation_status"] == "validated"
    assert creation.json()["data"]["validation_status"] == "validated"
    assert creation.json()["data"]["submission_id"] == "sub_27a_api_create"
    assert session.query(DataStandardPartnerSubmissionRecord).count() == 1


def test_partner_submission_api_trust_tier_is_registry_derived(
    api_client: TestClient,
    session: Session,
) -> None:
    reviewer_headers = _assign_role(
        api_client,
        session,
        AdminRole.DATA_REVIEWER,
        subject="auth0|layer27_trust_reviewer",
    )
    payload = _valid_submission(
        "sub_27a_trust_impersonation",
        partner_id="partner_acme_employer",
    )
    payload["trust_tier"] = "tier_1_verified_institutional"

    response = api_client.post(
        "/data-standards/partner-submissions",
        headers=reviewer_headers,
        json=payload,
    )

    assert response.status_code == 400
    assert session.query(DataStandardPartnerSubmissionRecord).count() == 0


def test_partner_registry_supports_required_types_statuses_and_trust_tiers() -> None:
    registry = DataStandardsService().partner_registry()

    assert set(registry.supported_partner_types) == {
        partner_type.value for partner_type in PartnerType
    }
    assert set(registry.verification_statuses) == {
        status.value for status in PartnerVerificationStatus
    }
    assert set(registry.trust_tiers) == {tier.value for tier in PartnerTrustTier}
    assert {partner.partner_type.value for partner in registry.partners} == {
        partner_type.value for partner_type in PartnerType
    }
    assert {partner.verification_status.value for partner in registry.partners} >= {
        status.value for status in PartnerVerificationStatus
    }


def test_partner_registry_records_include_required_public_safe_fields() -> None:
    registry = DataStandardsService().partner_registry()

    for partner in registry.partners:
        assert partner.partner_id
        assert partner.name
        assert partner.partner_type.value
        assert partner.region_scope
        assert partner.verification_status.value
        assert partner.allowed_submission_types
        assert partner.trust_tier.value
        assert partner.created_at
        assert partner.updated_at
        payload = partner.model_dump(mode="json")
        assert payload["public_contact_metadata"]
        assert "private_email" not in str(payload)
        assert "internal_contact" not in str(payload)
        assert "internal_review_notes" not in str(payload)
        assert "reviewer_identity" not in str(payload)


def test_partner_registry_api_routes_are_registered_and_reachable(
    api_client: TestClient,
) -> None:
    listing = api_client.get("/data-standards/partners")
    detail = api_client.get("/data-standards/partners/partner_state_university")

    assert listing.status_code == 200
    assert detail.status_code == 200
    assert listing.json()["data"]["partners"]
    assert detail.json()["data"]["partner_id"] == "partner_state_university"
    assert detail.json()["data"]["verification_status"] == "verified"


def test_required_quality_labels_exist_with_metadata_and_no_ranking_influence() -> None:
    labels = DataStandardsService().quality_labels().labels
    by_label = {label.label.value: label for label in labels}

    assert set(by_label) == {label.value for label in DataQualityLabelValue}
    for label in labels:
        assert label.display_name
        assert label.description
        assert label.allowed_sources
        assert label.minimum_confidence.value
        assert isinstance(label.requires_source_refs, bool)
        assert isinstance(label.requires_partner_verification, bool)
        assert label.ranking_influence_allowed is False
        assert label.public_display_allowed is True
        assert label.warning_copy
        assert label.trust_explanation is not None
        assert label.trust_explanation.ranking_influence_allowed is False
        assert label.trust_explanation.ranking_influence_label == (
            "Excluded from rankings"
        )

    assert by_label["low_confidence_signal"].warning_copy
    assert by_label["low_confidence_signal"].ranking_influence_allowed is False
    assert by_label["self_reported_employer_data"].warning_copy


def test_quality_label_api_route_serializes_required_metadata(
    api_client: TestClient,
) -> None:
    response = api_client.get("/data-standards/quality-labels")

    assert response.status_code == 200
    labels = {label["label"]: label for label in response.json()["data"]["labels"]}
    assert labels["verified_partner_data"]["requires_partner_verification"] is True
    assert labels["verified_partner_data"]["requires_source_refs"] is True
    assert labels["verified_partner_data"]["minimum_confidence"] == "medium"
    assert labels["low_confidence_signal"]["ranking_influence_allowed"] is False
    assert labels["low_confidence_signal"]["trust_explanation"]["trust_label"] == (
        "Excluded from rankings"
    )
    assert labels["low_confidence_signal"]["trust_explanation"][
        "ranking_influence_allowed"
    ] is False
    assert labels["low_confidence_signal"]["warning_copy"]


def test_verified_partner_data_requires_verified_partner_and_source_refs() -> None:
    service = DataStandardsService()

    eligible = service.evaluate_quality_label(
        _quality_eval_payload("verified_partner_data")
    )
    no_sources = service.evaluate_quality_label(
        {
            "label": "verified_partner_data",
            "partner_id": "partner_state_university",
            "confidence": {"confidence_label": "high"},
        }
    )
    pending_partner = service.evaluate_quality_label(
        _quality_eval_payload(
            "verified_partner_data",
            partner_id="partner_bootcamp_network",
        )
    )

    assert eligible.eligible is True
    assert eligible.partner_verification_status is PartnerVerificationStatus.VERIFIED
    assert eligible.ranking_influence_allowed is False
    assert no_sources.eligible is False
    assert "source_refs_required" in no_sources.reasons
    assert pending_partner.eligible is False
    assert "verified_partner_required" in pending_partner.reasons


def test_verified_partner_status_does_not_automatically_certify_submission() -> None:
    payload = _valid_submission(
        "sub_verified_partner_status_only",
        partner_id="partner_career_platform",
    )
    result = DataStandardsService().validate_submission(payload)
    evaluation = DataStandardsService().evaluate_quality_label(
        {
            "label": "verified_partner_data",
            "partner_id": "partner_career_platform",
        }
    )

    assert result.validation_status is PartnerValidationStatus.VALIDATED
    assert result.normalized_submission is not None
    assert result.normalized_submission.validation_status is PartnerValidationStatus.VALIDATED
    assert evaluation.eligible is False
    assert "source_refs_required" in evaluation.reasons


def test_quality_label_rule_examples_are_conservative() -> None:
    service = DataStandardsService()

    audited = service.evaluate_quality_label(
        {
            **_quality_eval_payload(
                "audited_source_data",
                partner_id=None,
                source_type="audited_partner_source",
            ),
            "audit_marker": "reviewed",
        }
    )
    employer = service.evaluate_quality_label(
        {
            **_quality_eval_payload(
                "self_reported_employer_data",
                partner_id="partner_acme_employer",
                source_type="employer_official",
                confidence_label="low",
            ),
            "submitter_type": "employer",
        }
    )
    public = service.evaluate_quality_label(
        _quality_eval_payload(
            "public_source_verified",
            partner_id=None,
            source_type="public_source",
        )
    )
    low = service.evaluate_quality_label(
        _quality_eval_payload(
            "low_confidence_signal",
            partner_id=None,
            confidence_label="low",
            freshness_status="stale",
        )
    )

    assert audited.eligible is True
    assert employer.eligible is True
    assert "self-reported employer data" in employer.warnings[0]
    assert public.eligible is True
    assert low.eligible is True
    for result in (audited, employer, public, low):
        assert result.ranking_influence_allowed is False


def test_quality_label_evaluation_serializes_freshness_confidence_and_source_expectations(
    api_client: TestClient,
) -> None:
    response = api_client.post(
        "/data-standards/quality-labels/evaluate",
        json=_quality_eval_payload(
            "public_source_verified",
            partner_id=None,
            source_type="public_source",
        ),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["eligible"] is True
    assert data["label"]["requires_source_refs"] is True
    assert data["label"]["ranking_influence_allowed"] is False
    assert data["label"]["trust_explanation"]["ranking_influence_label"] == (
        "Excluded from rankings"
    )
    assert data["source_ref_count"] == 1
    assert data["freshness"]["freshness_status"] == "fresh"
    assert data["confidence"]["confidence_label"] == "high"
    assert data["warnings"]


def test_quality_label_evaluation_does_not_mutate_canonical_tables(
    session: Session,
) -> None:
    before = _counts(session, CANONICAL_BOUNDARY_TABLES)

    service = DataStandardsService(session)
    service.partner_registry()
    service.quality_labels()
    service.evaluate_quality_label(_quality_eval_payload("verified_partner_data"))
    service.evaluate_quality_label(
        _quality_eval_payload(
            "low_confidence_signal",
            partner_id=None,
            confidence_label="unknown",
            freshness_status="unknown",
        )
    )
    session.flush()

    after = _counts(session, CANONICAL_BOUNDARY_TABLES)
    assert after == before
    assert session.query(DataStandardPartnerSubmissionRecord).count() == 0


def test_data_standards_payloads_do_not_leak_private_reviewer_or_contact_data(
    api_client: TestClient,
) -> None:
    partners = api_client.get("/data-standards/partners").json()["data"]
    labels = api_client.get("/data-standards/quality-labels").json()["data"]
    payload_text = f"{partners} {labels}".casefold()

    assert "private_email" not in payload_text
    assert "internal_contact" not in payload_text
    assert "internal_review_notes" not in payload_text
    assert "reviewer_identity" not in payload_text
    assert "admin_metadata" not in payload_text


def test_governance_framework_includes_required_areas_and_metadata() -> None:
    framework = DataStandardsService().governance_framework()
    by_area = {record.area.value: record for record in framework.governance_records}

    assert framework.status is GovernanceStatus.FRAMEWORK_DEFINED
    assert set(by_area) == {area.value for area in GovernanceArea}
    for record in framework.governance_records:
        assert record.display_name
        assert record.description
        assert record.review_questions
        assert record.risk_flags
        assert record.recommended_controls
        assert record.status is GovernanceStatus.FRAMEWORK_DEFINED
        assert record.version
        assert record.public_summary
        serialized = record.model_dump(mode="json")
        assert "board_active" not in str(serialized)
        assert "board_approved" not in str(serialized)
        assert "externally_governed" not in str(serialized)


def test_governance_framework_api_route_is_registered_and_serializes_metadata(
    api_client: TestClient,
) -> None:
    response = api_client.get("/data-standards/governance-framework")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "framework_defined"
    records = {record["area"]: record for record in data["governance_records"]}
    assert set(records) == {area.value for area in GovernanceArea}
    record = records["bias_review"]
    assert record["public_summary"]
    assert record["review_questions"]
    assert record["risk_flags"]
    assert record["recommended_controls"]
    assert record["status"] == "framework_defined"


def test_governance_framework_does_not_mutate_canonical_tables(
    session: Session,
) -> None:
    before = _counts(session, CANONICAL_BOUNDARY_TABLES)

    framework = DataStandardsService(session).governance_framework()
    session.flush()

    after = _counts(session, CANONICAL_BOUNDARY_TABLES)
    assert after == before
    assert framework.status is GovernanceStatus.FRAMEWORK_DEFINED
    assert session.query(DataStandardPartnerSubmissionRecord).count() == 0


def test_governance_does_not_auto_certify_submissions_or_quality_labels(
    session: Session,
) -> None:
    service = DataStandardsService(session)
    submission = service.create_submission(
        _valid_submission(
            "sub_governance_does_not_certify",
            partner_id="partner_career_platform",
        )
    )
    framework = service.governance_framework()
    evaluation = service.evaluate_quality_label(
        {
            "label": "verified_partner_data",
            "partner_id": "partner_career_platform",
        }
    )
    session.flush()

    assert submission.validation_status is PartnerValidationStatus.VALIDATED
    row = session.query(DataStandardPartnerSubmissionRecord).one()
    assert row.validation_status == "validated"
    assert framework.status is GovernanceStatus.FRAMEWORK_DEFINED
    assert evaluation.eligible is False
    assert "source_refs_required" in evaluation.reasons
