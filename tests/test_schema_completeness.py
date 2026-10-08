"""Verify the canonical schema covers every entity called out in DATA_MODEL.md."""

from sqlalchemy import inspect

from backend.shared.db import Base, create_all, import_all_models, make_engine

REQUIRED_TABLES = {
    "regions",
    "region_aliases",
    "region_canonical_redirects",
    "region_identity_claims",
    "region_state_memberships",
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
    "monetization_accounts",
    "monetization_plan_assignments",
    "monetization_usage_counters",
    "billing_customer_refs",
    "billing_subscription_refs",
    "billing_webhook_events",
    "organizations",
    "organization_memberships",
    "institutional_audit_logs",
    "institutional_reports",
    "institutional_data_requests",
    "integration_exports",
    "integration_reminders",
    "partner_import_batches",
    "partner_import_records",
    "api_clients",
    "api_keys",
    "api_usage_records",
    "api_access_audit_events",
    "career_platform_references",
    "career_platform_exports",
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
    "platform_api_keys",
    "platform_api_usage_events",
    "platform_api_audit_logs",
    "employer_programs",
    "opportunities",
    "opportunity_sources",
    "opportunity_region_bindings",
    "opportunity_role_family_bindings",
    "employer_influence_metadata",
    "opportunity_submissions",
    "opportunity_review_actions",
    "opportunity_data_sources",
    "opportunity_acquisition_runs",
    "opportunity_source_observations",
    "current_opportunities",
    "current_opportunity_source_links",
    "current_opportunity_identity_evidence",
    "opportunity_promotion_receipts",
    "opportunity_coverage_contracts",
    "career_memory_permissions",
    "career_memory_entries",
    "career_agent_tool_records",
    "career_agent_tool_audit_events",
    "career_identities",
    "career_identity_facts",
    "career_identity_imports",
    "career_decisions",
    "decision_context_snapshots",
    "decision_options",
    "decision_recommendations",
    "decision_versions",
    "career_action_plans",
    "career_actions",
    "career_applications",
    "career_application_transitions",
    "career_outcomes",
    "decision_factors",
    "longitudinal_context_snapshots",
    "decision_recommendation_evolutions",
    "decision_advisory_findings",
    "strategic_career_reviews",
    "data_standard_partner_submissions",
    "data_standard_candidate_facts",
    "data_standard_candidate_reviews",
    "data_standard_canonical_merges",
    "trust_assessments",
    "risk_routing_decisions",
    "user_reports",
    "automated_recheck_jobs",
    "exception_cases",
    "product_analytics_events",
    "product_user_visits",
    "beta_cohorts",
    "beta_cohort_memberships",
    "product_feature_gates",
    "experiment_assignments",
    "recommendation_feedback",
    "decision_reflections",
    "strategy_changes",
    "support_cases",
    "support_case_events",
    "product_entitlement_grants",
    "commercial_experiment_signals",
}

# Every canonical truth/output object must carry these metadata columns
# (DATA_MODEL.md §2 + §10 + Layer 3 provenance records).
CANONICAL_METADATA_COLUMNS = {"state", "version", "created_at", "updated_at"}

APPEND_ONLY_LOG_TABLES = {
    "admin_event_logs",
    "institutional_audit_logs",
    "product_analytics_events",
    "support_case_events",
}
VISIT_TELEMETRY_TABLES = {"product_user_visits"}
HISTORICAL_INTELLIGENCE_TABLES = {
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
}
ADMIN_REVIEW_TABLES = {
    "audit_finding_reviews",
    "admin_overrides",
    "admin_repair_actions",
}
CANONICAL_METADATA_TABLES = (
    REQUIRED_TABLES
    - {"jobs"}
    - APPEND_ONLY_LOG_TABLES
    - VISIT_TELEMETRY_TABLES
    - HISTORICAL_INTELLIGENCE_TABLES
    - ADMIN_REVIEW_TABLES
)  # jobs, logs, and history rows carry their own metadata shapes
USER_IDENTITY_TABLES = {
    "users",
    "external_auth_identities",
    "user_profiles",
    "user_preference_profiles",
    "saved_market_artifacts",
    "personalized_recommendation_snapshots",
    "user_alerts",
    "career_memory_permissions",
    "career_memory_entries",
    "career_agent_tool_records",
    "career_agent_tool_audit_events",
    "career_identities",
    "career_identity_facts",
    "career_identity_imports",
    "career_decisions",
    "decision_context_snapshots",
    "decision_options",
    "decision_recommendations",
    "decision_versions",
    "career_action_plans",
    "career_actions",
    "career_applications",
    "career_application_transitions",
    "career_outcomes",
    "decision_factors",
    "longitudinal_context_snapshots",
    "decision_recommendation_evolutions",
    "decision_advisory_findings",
    "strategic_career_reviews",
    "product_user_visits",
    "beta_cohort_memberships",
    "experiment_assignments",
    "recommendation_feedback",
    "decision_reflections",
    "strategy_changes",
    "support_cases",
    "product_entitlement_grants",
    "commercial_experiment_signals",
}
SYSTEM_EVENT_TABLES = {"alert_events"}
GEOGRAPHY_LOOKUP_TABLES = {
    "region_aliases",
    "region_canonical_redirects",
    "region_identity_claims",
    "region_state_memberships",
}
OPERATOR_WORKFLOW_TABLES = {"region_expansion_workflows", "beta_cohorts", "product_feature_gates"}
MONETIZATION_TABLES = {
    "monetization_accounts",
    "monetization_plan_assignments",
    "monetization_usage_counters",
}
BILLING_TABLES = {
    "billing_customer_refs",
    "billing_subscription_refs",
    "billing_webhook_events",
}
INSTITUTIONAL_TABLES = {
    "organizations",
    "organization_memberships",
    "institutional_reports",
    "institutional_data_requests",
}
INTEGRATION_TABLES = {
    "integration_exports",
    "integration_reminders",
    "partner_import_batches",
    "partner_import_records",
    "api_clients",
    "api_keys",
    "api_usage_records",
    "api_access_audit_events",
    "career_platform_references",
    "career_platform_exports",
}
PLATFORM_API_TABLES = {
    "platform_api_keys",
    "platform_api_usage_events",
    "platform_api_audit_logs",
}
OPPORTUNITY_TABLES = {
    "employer_programs",
    "opportunities",
    "opportunity_sources",
    "opportunity_region_bindings",
    "opportunity_role_family_bindings",
    "employer_influence_metadata",
    "opportunity_submissions",
    "opportunity_review_actions",
    "opportunity_data_sources",
    "opportunity_acquisition_runs",
    "opportunity_source_observations",
    "current_opportunities",
    "current_opportunity_source_links",
    "current_opportunity_identity_evidence",
    "opportunity_promotion_receipts",
    "opportunity_coverage_contracts",
}
DATA_STANDARDS_TABLES = {
    "data_standard_partner_submissions",
    "data_standard_candidate_facts",
    "data_standard_candidate_reviews",
    "data_standard_canonical_merges",
}
TRUST_SNAPSHOT_TABLES = {
    "trust_assessments",
    "risk_routing_decisions",
    "user_reports",
    "automated_recheck_jobs",
    "exception_cases",
}
MARKET_CANONICAL_METADATA_TABLES = CANONICAL_METADATA_TABLES - USER_IDENTITY_TABLES
MARKET_CANONICAL_METADATA_TABLES = (
    MARKET_CANONICAL_METADATA_TABLES - SYSTEM_EVENT_TABLES - OPERATOR_WORKFLOW_TABLES
)
MARKET_CANONICAL_METADATA_TABLES = MARKET_CANONICAL_METADATA_TABLES - GEOGRAPHY_LOOKUP_TABLES
MARKET_CANONICAL_METADATA_TABLES = MARKET_CANONICAL_METADATA_TABLES - MONETIZATION_TABLES
MARKET_CANONICAL_METADATA_TABLES = MARKET_CANONICAL_METADATA_TABLES - BILLING_TABLES
MARKET_CANONICAL_METADATA_TABLES = MARKET_CANONICAL_METADATA_TABLES - INSTITUTIONAL_TABLES
MARKET_CANONICAL_METADATA_TABLES = MARKET_CANONICAL_METADATA_TABLES - INTEGRATION_TABLES
MARKET_CANONICAL_METADATA_TABLES = MARKET_CANONICAL_METADATA_TABLES - PLATFORM_API_TABLES
MARKET_CANONICAL_METADATA_TABLES = MARKET_CANONICAL_METADATA_TABLES - OPPORTUNITY_TABLES
MARKET_CANONICAL_METADATA_TABLES = MARKET_CANONICAL_METADATA_TABLES - DATA_STANDARDS_TABLES
MARKET_CANONICAL_METADATA_TABLES = MARKET_CANONICAL_METADATA_TABLES - TRUST_SNAPSHOT_TABLES


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


def test_monetization_tables_have_safe_account_state_columns() -> None:
    engine = make_engine("sqlite:///:memory:")
    create_all(engine)
    inspector = inspect(engine)

    account_cols = {c["name"] for c in inspector.get_columns("monetization_accounts")}
    assert {
        "monetization_account_id",
        "user_id",
        "account_type",
        "assigned_seats_count",
        "safe_metadata",
        "created_at",
        "updated_at",
    }.issubset(account_cols)
    assert {"stripe_customer_id", "payment_provider", "recommendation_inputs"}.isdisjoint(
        account_cols
    )

    assignment_cols = {c["name"] for c in inspector.get_columns("monetization_plan_assignments")}
    assert {
        "plan_assignment_id",
        "monetization_account_id",
        "plan_key",
        "plan_status",
        "assignment_source",
        "effective_at",
        "expires_at",
        "seat_limit",
        "safe_metadata",
        "created_at",
        "updated_at",
    }.issubset(assignment_cols)
    assert {"stripe_subscription_id", "provider_subscription_id"}.isdisjoint(assignment_cols)

    usage_cols = {c["name"] for c in inspector.get_columns("monetization_usage_counters")}
    assert {
        "usage_counter_id",
        "monetization_account_id",
        "feature_key",
        "period_start",
        "period_end",
        "used_count",
        "limit_count",
        "reset_policy",
        "last_incremented_at",
        "created_at",
        "updated_at",
    }.issubset(usage_cols)


def test_billing_tables_isolate_provider_references_from_entitlements() -> None:
    engine = make_engine("sqlite:///:memory:")
    create_all(engine)
    inspector = inspect(engine)

    customer_cols = {c["name"] for c in inspector.get_columns("billing_customer_refs")}
    assert {
        "billing_customer_ref_id",
        "monetization_account_id",
        "provider",
        "provider_customer_id",
        "safe_metadata",
        "created_at",
        "updated_at",
    }.issubset(customer_cols)

    subscription_cols = {c["name"] for c in inspector.get_columns("billing_subscription_refs")}
    assert {
        "billing_subscription_ref_id",
        "monetization_account_id",
        "provider",
        "provider_subscription_id",
        "provider_customer_id",
        "provider_price_id",
        "plan_key",
        "provider_status",
        "current_period_end",
        "canceled_at",
        "active_plan_assignment_id",
        "safe_metadata",
        "created_at",
        "updated_at",
    }.issubset(subscription_cols)

    webhook_cols = {c["name"] for c in inspector.get_columns("billing_webhook_events")}
    assert {
        "billing_webhook_event_id",
        "provider",
        "provider_event_id",
        "event_type",
        "processing_status",
        "received_at",
        "processed_at",
        "error_code",
        "safe_metadata",
    }.issubset(webhook_cols)


def test_institutional_tables_have_scoped_permission_columns() -> None:
    engine = make_engine("sqlite:///:memory:")
    create_all(engine)
    inspector = inspect(engine)

    org_cols = {c["name"] for c in inspector.get_columns("organizations")}
    assert {
        "organization_id",
        "name",
        "organization_type",
        "status",
        "created_at",
        "updated_at",
    }.issubset(org_cols)

    membership_cols = {c["name"] for c in inspector.get_columns("organization_memberships")}
    assert {
        "organization_membership_id",
        "organization_id",
        "user_id",
        "role",
        "status",
        "created_at",
        "updated_at",
    }.issubset(membership_cols)

    audit_cols = {c["name"] for c in inspector.get_columns("institutional_audit_logs")}
    assert {
        "institutional_audit_log_id",
        "organization_id",
        "actor_user_id",
        "actor_role",
        "action",
        "target_type",
        "target_id",
        "purpose",
        "metadata",
        "created_at",
    }.issubset(audit_cols)

    report_cols = {c["name"] for c in inspector.get_columns("institutional_reports")}
    assert {
        "institutional_report_id",
        "organization_id",
        "report_type",
        "title",
        "generated_by_user_id",
        "generated_at",
        "payload_json",
        "minimum_group_size",
        "privacy_summary",
        "coverage_summary",
        "status",
        "created_at",
        "updated_at",
    }.issubset(report_cols)

    data_request_cols = {c["name"] for c in inspector.get_columns("institutional_data_requests")}
    assert {
        "institutional_data_request_id",
        "organization_id",
        "requester_user_id",
        "request_type",
        "subject_type",
        "subject_user_id",
        "status",
        "reason",
        "resolved_at",
        "metadata",
        "created_at",
        "updated_at",
    }.issubset(data_request_cols)


def test_integration_tables_preserve_noncanonical_boundaries() -> None:
    engine = make_engine("sqlite:///:memory:")
    create_all(engine)
    inspector = inspect(engine)

    batch_cols = {c["name"] for c in inspector.get_columns("partner_import_batches")}
    assert {
        "partner_import_batch_id",
        "organization_id",
        "uploaded_by_user_id",
        "source_type",
        "status",
        "import_format",
        "source_attribution",
        "raw_payload_text",
        "record_count",
        "accepted_record_count",
        "quarantined_record_count",
        "rejected_record_count",
        "validation_result_json",
        "receipt_json",
        "governance_warnings_json",
        "created_at",
        "updated_at",
    }.issubset(batch_cols)
    assert {"state", "version", "canonical_company_id", "canonical_region_id"}.isdisjoint(
        batch_cols
    )

    record_cols = {c["name"] for c in inspector.get_columns("partner_import_records")}
    assert {
        "partner_import_record_id",
        "partner_import_batch_id",
        "organization_id",
        "record_index",
        "source_type",
        "record_status",
        "decision",
        "source_attribution",
        "employer_name",
        "region_label",
        "confidence",
        "freshness_status",
        "partner_payload_json",
        "evidence_json",
        "validation_warnings_json",
        "created_at",
        "updated_at",
    }.issubset(record_cols)
    assert {"state", "version", "raw_total_score", "score_ruleset_version"}.isdisjoint(record_cols)

    api_client_cols = {c["name"] for c in inspector.get_columns("api_clients")}
    assert {
        "api_client_id",
        "display_name",
        "created_by_user_id",
        "organization_id",
        "status",
        "scopes_json",
        "allowed_origins_json",
        "rate_limit_count",
        "rate_limit_window_seconds",
        "created_at",
        "updated_at",
    }.issubset(api_client_cols)
    assert {"raw_key", "access_token", "refresh_token", "ats_pipeline_scope"}.isdisjoint(
        api_client_cols
    )

    api_key_cols = {c["name"] for c in inspector.get_columns("api_keys")}
    assert {
        "api_key_id",
        "api_client_id",
        "created_by_user_id",
        "key_prefix",
        "key_hash",
        "display_key",
        "status",
        "last_used_at",
        "revoked_at",
        "created_at",
        "updated_at",
    }.issubset(api_key_cols)
    assert {"raw_key", "token", "secret"}.isdisjoint(api_key_cols)

    usage_cols = {c["name"] for c in inspector.get_columns("api_usage_records")}
    assert {
        "api_usage_record_id",
        "api_client_id",
        "api_key_id",
        "route",
        "method",
        "scope",
        "decision",
        "status_code",
        "rate_limit_limit",
        "rate_limit_remaining",
        "rate_limit_reset_at",
        "occurred_at",
    }.issubset(usage_cols)

    career_export_cols = {c["name"] for c in inspector.get_columns("career_platform_exports")}
    assert {
        "career_platform_export_id",
        "created_by_user_id",
        "organization_id",
        "platform",
        "risk_posture",
        "export_mode",
        "rows_json",
        "receipt_json",
        "manual_only",
        "automation_performed",
        "ats_state_created",
        "application_status_created",
        "recruiter_outreach_created",
        "created_at",
        "updated_at",
    }.issubset(career_export_cols)
    assert {"application_status", "resume_payload", "recruiter_message"}.isdisjoint(
        career_export_cols
    )


def test_platform_api_tables_preserve_external_access_boundaries() -> None:
    engine = make_engine("sqlite:///:memory:")
    create_all(engine)
    inspector = inspect(engine)

    key_cols = {c["name"] for c in inspector.get_columns("platform_api_keys")}
    assert {
        "platform_api_key_id",
        "key_prefix",
        "key_hash",
        "display_key",
        "label",
        "status",
        "environment",
        "tier",
        "product_scopes_json",
        "last_used_at",
        "revoked_at",
        "created_at",
        "updated_at",
    }.issubset(key_cols)
    assert {
        "raw_key",
        "token",
        "secret",
        "billing_record",
        "user_id",
        "institution_id",
        "raw_job_record",
    }.isdisjoint(key_cols)

    usage_cols = {c["name"] for c in inspector.get_columns("platform_api_usage_events")}
    assert {
        "platform_api_usage_event_id",
        "platform_api_key_id",
        "key_prefix",
        "product_id",
        "endpoint",
        "method",
        "request_units",
        "status_code",
        "outcome",
        "decision_reason",
        "occurred_at",
    }.issubset(usage_cols)
    assert {"raw_key", "raw_job_record", "billing_record", "ingestion_metadata"}.isdisjoint(
        usage_cols
    )

    audit_cols = {c["name"] for c in inspector.get_columns("platform_api_audit_logs")}
    assert {
        "platform_api_audit_log_id",
        "platform_api_key_id",
        "key_prefix",
        "product_id",
        "endpoint",
        "method",
        "event_type",
        "decision",
        "status_code",
        "metadata",
        "occurred_at",
    }.issubset(audit_cols)
    assert {"raw_key", "token", "secret", "raw_scrape_record"}.isdisjoint(audit_cols)


def test_historical_intelligence_tables_are_append_only_records() -> None:
    engine = make_engine("sqlite:///:memory:")
    create_all(engine)
    inspector = inspect(engine)

    for table_name in HISTORICAL_INTELLIGENCE_TABLES:
        cols = {c["name"] for c in inspector.get_columns(table_name)}
        assert "created_at" in cols
        assert "updated_at" not in cols
        assert "state" not in cols
        if table_name != "market_index_versions":
            assert "version" not in cols

    market_cols = {c["name"] for c in inspector.get_columns("market_snapshots")}
    assert {
        "market_snapshot_id",
        "region_id",
        "snapshot_date",
        "snapshot_type",
        "overall_score",
        "entry_level_access_score",
        "internship_density_score",
        "ai_opportunity_score",
        "product_opportunity_score",
        "company_presence_score",
        "hidden_opportunity_score",
        "coverage_tier",
        "freshness_state",
        "confidence_score",
        "warnings",
        "provenance_summary",
        "created_at",
    }.issubset(market_cols)

    observation_cols = {c["name"] for c in inspector.get_columns("historical_observations")}
    assert {
        "historical_observation_id",
        "observation_type",
        "target_type",
        "target_id",
        "region_id",
        "previous_snapshot_id",
        "current_snapshot_id",
        "delta_value",
        "delta_direction",
        "severity",
        "confidence_score",
        "evidence_summary",
        "created_at",
    }.issubset(observation_cols)

    signal_cols = {c["name"] for c in inspector.get_columns("predictive_signals")}
    assert {
        "predictive_signal_id",
        "signal_type",
        "target_type",
        "target_id",
        "region_id",
        "signal_strength",
        "confidence_level",
        "evidence_window_start",
        "evidence_window_end",
        "snapshot_count",
        "minimum_snapshot_count_met",
        "summary",
        "warnings",
        "status",
        "created_at",
        "expires_at",
    }.issubset(signal_cols)

    index_version_cols = {c["name"] for c in inspector.get_columns("market_index_versions")}
    assert {
        "market_index_version_id",
        "index_id",
        "version",
        "formula_description",
        "input_schema",
        "internal_weight_config",
        "status",
        "effective_date",
        "created_at",
    }.issubset(index_version_cols)

    index_score_cols = {c["name"] for c in inspector.get_columns("market_index_scores")}
    assert {
        "market_index_score_id",
        "index_id",
        "index_version_id",
        "region_id",
        "score",
        "rank",
        "confidence_score",
        "freshness_state",
        "evidence_summary",
        "calculated_at",
        "created_at",
    }.issubset(index_score_cols)

    report_cols = {c["name"] for c in inspector.get_columns("benchmark_reports")}
    assert {
        "benchmark_report_id",
        "report_key",
        "title",
        "report_period",
        "report_type",
        "status",
        "summary",
        "methodology_summary",
        "data_window_start",
        "data_window_end",
        "freshness_notes",
        "confidence_notes",
        "coverage_notes",
        "limitations",
        "created_at",
        "published_at",
        "archived_at",
        "superseded_at",
    }.issubset(report_cols)

    report_ranking_cols = {c["name"] for c in inspector.get_columns("benchmark_report_rankings")}
    assert {
        "benchmark_report_ranking_id",
        "report_id",
        "region_id",
        "rank",
        "score",
        "index_score_id",
        "explanation",
        "warnings",
        "confidence_score",
        "freshness_state",
        "created_at",
    }.issubset(report_ranking_cols)

    contribution_cols = {c["name"] for c in inspector.get_columns("data_contributions")}
    assert {
        "data_contribution_id",
        "contributor_type",
        "contributor_id",
        "institution_id",
        "target_type",
        "target_id",
        "region_id",
        "contribution_type",
        "structured_payload",
        "summary",
        "claimed_confidence",
        "status",
        "created_at",
        "reviewed_at",
    }.issubset(contribution_cols)

    contribution_evidence_cols = {c["name"] for c in inspector.get_columns("contribution_evidence")}
    assert {
        "contribution_evidence_id",
        "contribution_id",
        "evidence_type",
        "url",
        "reference",
        "description",
        "uploaded_reference_id",
        "created_at",
    }.issubset(contribution_evidence_cols)

    contribution_review_cols = {c["name"] for c in inspector.get_columns("contribution_reviews")}
    assert {
        "contribution_review_id",
        "contribution_id",
        "reviewer_id",
        "review_decision",
        "review_notes",
        "canonical_update_candidate_created",
        "canonical_update_candidate_ref",
        "refresh_task_created",
        "refresh_task_ref",
        "created_at",
    }.issubset(contribution_review_cols)


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
    assert has_unique_pair("monetization_accounts", ("user_id",))
    assert has_unique_pair(
        "monetization_usage_counters",
        ("monetization_account_id", "feature_key", "period_start", "period_end"),
    )


def test_metadata_registry_has_no_extra_tables() -> None:
    """Registered tables should match the implemented canonical schema."""
    import_all_models()
    declared = set(Base.metadata.tables.keys())
    assert declared == REQUIRED_TABLES, declared.symmetric_difference(REQUIRED_TABLES)
