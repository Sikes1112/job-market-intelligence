"""Verify the canonical schema covers every entity called out in DATA_MODEL.md."""

from sqlalchemy import inspect

from backend.shared.db import Base, create_all, import_all_models, make_engine

REQUIRED_TABLES = {
    "regions",
    "companies",
    "company_region_presence",
    "company_region_hiring",
    "company_region_entry_level",
    "region_market_scores",
    "raw_ingestion_records",
    "source_refs",
    "source_observations",
    "fact_source_links",
    "jobs",
    "output_metadata",
    "users",
    "external_auth_identities",
    "user_profiles",
    "user_preference_profiles",
    "saved_market_artifacts",
    "personalized_recommendation_snapshots",
    "alert_events",
    "user_alerts",
    "region_expansion_workflows",
    "admin_event_logs",
    "audit_finding_reviews",
    "admin_overrides",
    "admin_repair_actions",
}

# Every canonical truth/output object must carry these metadata columns
# (DATA_MODEL.md §2 + §10 + Layer 3 provenance records).
CANONICAL_METADATA_COLUMNS = {"state", "version", "created_at", "updated_at"}

APPEND_ONLY_LOG_TABLES = {"admin_event_logs"}
ADMIN_REVIEW_TABLES = {
    "audit_finding_reviews",
    "admin_overrides",
    "admin_repair_actions",
}
CANONICAL_METADATA_TABLES = (
    REQUIRED_TABLES - {"jobs"} - APPEND_ONLY_LOG_TABLES - ADMIN_REVIEW_TABLES
)  # jobs and admin logs carry their own metadata shapes
USER_IDENTITY_TABLES = {
    "users",
    "external_auth_identities",
    "user_profiles",
    "user_preference_profiles",
    "saved_market_artifacts",
    "personalized_recommendation_snapshots",
    "user_alerts",
}
SYSTEM_EVENT_TABLES = {"alert_events"}
OPERATOR_WORKFLOW_TABLES = {"region_expansion_workflows"}
MARKET_CANONICAL_METADATA_TABLES = CANONICAL_METADATA_TABLES - USER_IDENTITY_TABLES
MARKET_CANONICAL_METADATA_TABLES = (
    MARKET_CANONICAL_METADATA_TABLES - SYSTEM_EVENT_TABLES - OPERATOR_WORKFLOW_TABLES
)


def test_all_required_tables_registered() -> None:
    engine = make_engine("sqlite:///:memory:")
    create_all(engine)
    inspector = inspect(engine)
    found = set(inspector.get_table_names())
    assert REQUIRED_TABLES.issubset(found), REQUIRED_TABLES - found


def test_canonical_metadata_columns_present() -> None:
    engine = make_engine("sqlite:///:memory:")
    create_all(engine)
    inspector = inspect(engine)
    missing: dict[str, set[str]] = {}
    for table_name in MARKET_CANONICAL_METADATA_TABLES:
        cols = {c["name"] for c in inspector.get_columns(table_name)}
        gaps = CANONICAL_METADATA_COLUMNS - cols
        if gaps:
            missing[table_name] = gaps
    assert not missing, missing


def test_user_identity_tables_have_timestamps() -> None:
    engine = make_engine("sqlite:///:memory:")
    create_all(engine)
    inspector = inspect(engine)
    for table_name in USER_IDENTITY_TABLES:
        cols = {c["name"] for c in inspector.get_columns(table_name)}
        assert {"created_at", "updated_at"}.issubset(cols)


def test_jobs_table_has_envelope_columns() -> None:
    engine = make_engine("sqlite:///:memory:")
    create_all(engine)
    inspector = inspect(engine)
    cols = {c["name"] for c in inspector.get_columns("jobs")}
    expected = {
        "job_id",
        "job_type",
        "queue_name",
        "status",
        "priority",
        "scope_hash",
        "dedupe_key",
        "retry_count",
        "max_retries",
        "input_hash",
        "output_hash",
        "dependency_refs",
        "started_at",
        "completed_at",
        "created_at",
        "updated_at",
        "error_code",
        "error_message",
        "warnings",
    }
    missing = expected - cols
    assert not missing, missing


def test_admin_event_log_has_append_only_columns() -> None:
    engine = make_engine("sqlite:///:memory:")
    create_all(engine)
    inspector = inspect(engine)
    cols = {c["name"] for c in inspector.get_columns("admin_event_logs")}
    expected = {
        "admin_event_id",
        "actor",
        "actor_role",
        "action",
        "object_type",
        "object_id",
        "before_state",
        "after_state",
        "reason",
        "timestamp",
        "request_id",
    }
    missing = expected - cols
    assert not missing, missing
    assert "updated_at" not in cols


def test_audit_finding_review_has_lifecycle_columns() -> None:
    engine = make_engine("sqlite:///:memory:")
    create_all(engine)
    inspector = inspect(engine)
    cols = {c["name"] for c in inspector.get_columns("audit_finding_reviews")}
    expected = {
        "finding_id",
        "review_state",
        "category",
        "severity",
        "scope_type",
        "scope_ref",
        "message",
        "evidence_refs",
        "recommendation",
        "created_at",
        "updated_at",
        "last_transitioned_at",
        "last_transition_actor",
        "last_transition_role",
        "last_transition_reason",
    }
    missing = expected - cols
    assert not missing, missing


def test_admin_overrides_have_workflow_columns() -> None:
    engine = make_engine("sqlite:///:memory:")
    create_all(engine)
    inspector = inspect(engine)
    cols = {c["name"] for c in inspector.get_columns("admin_overrides")}
    expected = {
        "override_id",
        "target_type",
        "target_id",
        "override_type",
        "previous_value",
        "override_value",
        "reason",
        "reviewer_actor",
        "reviewer_role",
        "source_evidence",
        "expires_at",
        "review_at",
        "status",
        "created_at",
        "updated_at",
        "activated_at",
        "activated_by",
        "activated_role",
        "revoked_at",
        "revoked_by",
        "revoked_role",
        "revocation_reason",
    }
    missing = expected - cols
    assert not missing, missing


def test_admin_repair_actions_have_workflow_columns() -> None:
    engine = make_engine("sqlite:///:memory:")
    create_all(engine)
    inspector = inspect(engine)
    cols = {c["name"] for c in inspector.get_columns("admin_repair_actions")}
    expected = {
        "repair_action_id",
        "action_type",
        "target_type",
        "target_id",
        "status",
        "reason",
        "requested_by",
        "requested_role",
        "requested_at",
        "executed_by",
        "executed_role",
        "executed_at",
        "audit_finding_id",
        "parameters",
        "result",
        "created_at",
        "updated_at",
    }
    missing = expected - cols
    assert not missing, missing


def test_alert_tables_have_reference_only_columns() -> None:
    engine = make_engine("sqlite:///:memory:")
    create_all(engine)
    inspector = inspect(engine)

    event_cols = {c["name"] for c in inspector.get_columns("alert_events")}
    assert {
        "alert_event_id",
        "event_type",
        "company_id",
        "region_id",
        "role_family",
        "previous_value",
        "new_value",
        "change_summary",
        "freshness_status",
        "freshness_observed_at",
        "freshness_expires_at",
        "source_refs",
        "change_basis_refs",
        "detection_basis",
        "created_at",
    }.issubset(event_cols)
    assert {"company_name", "region_detail", "market_output"}.isdisjoint(event_cols)

    user_alert_cols = {c["name"] for c in inspector.get_columns("user_alerts")}
    assert {
        "user_alert_id",
        "user_id",
        "alert_event_id",
        "relevance_reason",
        "relevance_artifact_id",
        "relevance_artifact_type",
        "relevance_artifact_ref",
        "is_read",
        "dismissed",
        "created_at",
        "updated_at",
        "read_at",
        "dismissed_at",
    }.issubset(user_alert_cols)


def test_region_expansion_workflow_has_required_checklist_columns() -> None:
    engine = make_engine("sqlite:///:memory:")
    create_all(engine)
    inspector = inspect(engine)
    cols = {c["name"] for c in inspector.get_columns("region_expansion_workflows")}
    expected = {
        "workflow_id",
        "region_key",
        "display_name",
        "canonical_region_id",
        "workflow_state",
        "region_data_mode",
        "published",
        "refresh_enabled",
        "ingestion_contract_ref",
        "provenance_contract_ref",
        "admin_review_ref",
        "output_refresh_contract_ref",
        "checklist_notes",
        "region_identity_check",
        "source_coverage_check",
        "company_region_presence_check",
        "hiring_signal_support_check",
        "entry_level_signal_support_check",
        "scoring_readiness_check",
        "freshness_readiness_check",
        "provenance_attached_check",
        "admin_approval_check",
        "output_refresh_readiness_check",
        "created_at",
        "updated_at",
    }
    missing = expected - cols
    assert not missing, missing


def test_pair_uniqueness_indexes_exist() -> None:
    engine = make_engine("sqlite:///:memory:")
    create_all(engine)
    inspector = inspect(engine)

    def has_unique_pair(table: str, columns: tuple[str, ...]) -> bool:
        for uq in inspector.get_unique_constraints(table):
            if tuple(uq["column_names"]) == columns:
                return True
        return False

    assert has_unique_pair("company_region_presence", ("company_id", "region_id"))
    assert has_unique_pair("company_region_hiring", ("company_id", "region_id"))
    assert has_unique_pair("company_region_entry_level", ("company_id", "region_id"))
    assert has_unique_pair("region_market_scores", ("region_id",))
    assert has_unique_pair("output_metadata", ("output_type", "subject_id"))
    assert has_unique_pair(
        "saved_market_artifacts",
        ("user_id", "artifact_type", "artifact_ref"),
    )
    assert has_unique_pair("user_alerts", ("user_id", "alert_event_id"))
    assert has_unique_pair("region_expansion_workflows", ("region_key",))


def test_metadata_registry_has_no_extra_tables() -> None:
    """Registered tables should match the implemented canonical schema."""
    import_all_models()
    declared = set(Base.metadata.tables.keys())
    assert declared == REQUIRED_TABLES, declared.symmetric_difference(REQUIRED_TABLES)
