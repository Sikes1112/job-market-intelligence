from backend.shared.provenance import (
    DEMO_DATA_ORIGINS,
    FRESHNESS_WINDOWS,
    REAL_DATA_ORIGINS,
    SOURCE_TYPE_DEFAULT_ACCEPTABILITY,
    DataOrigin,
    FactBindingType,
    FreshnessCategory,
    LicenseTermsCategory,
    ObservationStatus,
    ProvenanceFactType,
    SourceAcceptability,
    SourceType,
)


def test_canonical_data_origin_values_exist() -> None:
    assert DataOrigin.values() == {
        "demo_seed",
        "synthetic_or_curated_demo",
        "real_observed",
        "real_derived",
        "manual_reviewed",
        "unknown_origin",
    }


def test_observation_status_distinguishes_unknown_and_zero() -> None:
    assert ObservationStatus.values() == {
        "unknown",
        "zero_observed",
        "positive_observed",
        "not_applicable",
        "not_collected",
        "stale",
        "conflicting",
        "low_confidence",
    }
    assert ObservationStatus.UNKNOWN.value == "unknown"
    assert ObservationStatus.ZERO_OBSERVED.value == "zero_observed"
    assert ObservationStatus.UNKNOWN is not ObservationStatus.ZERO_OBSERVED


def test_seed_demo_and_real_observed_are_distinct_origins() -> None:
    assert DataOrigin.DEMO_SEED is not DataOrigin.REAL_OBSERVED
    assert DataOrigin.DEMO_SEED in DEMO_DATA_ORIGINS
    assert DataOrigin.REAL_OBSERVED in REAL_DATA_ORIGINS


def test_source_acceptability_categories_exist() -> None:
    assert SourceAcceptability.values() == {
        "allowed",
        "allowed_with_caution",
        "manual_review_required",
        "disallowed",
    }


def test_source_type_values_exist() -> None:
    assert SourceType.values() == {
        "company_official",
        "ats_job_board",
        "government_public_data",
        "university_or_coop_board",
        "regional_economic_dataset",
        "reputable_third_party_aggregator",
        "manual_research",
        "user_submitted",
        "llm_generated",
        "unknown_source",
    }


def test_license_terms_categories_exist() -> None:
    assert LicenseTermsCategory.values() == {
        "public",
        "permissive",
        "restricted",
        "unknown",
        "prohibited",
    }


def test_freshness_categories_exist() -> None:
    assert FreshnessCategory.values() == {
        "fast_changing",
        "seasonal",
        "medium_changing",
        "slow_changing",
    }


def test_provenance_fact_types_exist() -> None:
    assert ProvenanceFactType.values() == {
        "company_universe",
        "company_presence",
        "hiring_counts",
        "internships_coops",
        "early_career_programs",
        "region_metadata",
    }


def test_fact_binding_types_exist() -> None:
    assert FactBindingType.values() == {
        "company",
        "region",
        "company_region_presence",
        "company_region_hiring",
        "company_region_entry_level",
        "score_input",
    }


def test_freshness_windows_exist_for_required_data_types() -> None:
    assert FRESHNESS_WINDOWS[ProvenanceFactType.COMPANY_PRESENCE].category is (
        FreshnessCategory.SLOW_CHANGING
    )
    assert FRESHNESS_WINDOWS[ProvenanceFactType.HIRING_COUNTS].category is (
        FreshnessCategory.FAST_CHANGING
    )
    assert FRESHNESS_WINDOWS[ProvenanceFactType.INTERNSHIPS_COOPS].category is (
        FreshnessCategory.SEASONAL
    )
    assert FRESHNESS_WINDOWS[ProvenanceFactType.EARLY_CAREER_PROGRAMS].category is (
        FreshnessCategory.MEDIUM_CHANGING
    )
    assert FRESHNESS_WINDOWS[ProvenanceFactType.REGION_METADATA].category is (
        FreshnessCategory.SLOW_CHANGING
    )

    for fact_type in (
        ProvenanceFactType.COMPANY_PRESENCE,
        ProvenanceFactType.HIRING_COUNTS,
        ProvenanceFactType.INTERNSHIPS_COOPS,
        ProvenanceFactType.EARLY_CAREER_PROGRAMS,
        ProvenanceFactType.REGION_METADATA,
    ):
        assert FRESHNESS_WINDOWS[fact_type].max_age_days > 0


def test_llm_generated_is_not_allowed_factual_source_category() -> None:
    assert SOURCE_TYPE_DEFAULT_ACCEPTABILITY[SourceType.LLM_GENERATED] is (
        SourceAcceptability.DISALLOWED
    )
    assert SOURCE_TYPE_DEFAULT_ACCEPTABILITY[SourceType.LLM_GENERATED] is not (
        SourceAcceptability.ALLOWED
    )


def test_synthetic_or_curated_demo_is_not_treated_as_real_observed() -> None:
    assert DataOrigin.SYNTHETIC_OR_CURATED_DEMO is not DataOrigin.REAL_OBSERVED
    assert DataOrigin.SYNTHETIC_OR_CURATED_DEMO in DEMO_DATA_ORIGINS
    assert DataOrigin.SYNTHETIC_OR_CURATED_DEMO not in REAL_DATA_ORIGINS
