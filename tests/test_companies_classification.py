from backend.companies.classification import (
    DEFAULT_MAG7,
    DefaultEligibilityRule,
    DefaultMajorTechRule,
    Mag7List,
)
from backend.companies.service import CompanyDefinition
from backend.companies.types import (
    ClassificationConfidence,
    EligibilityStatus,
)


def _def(**overrides) -> CompanyDefinition:
    base = dict(
        company_id="c1",
        company_name="Example",
        normalized_company_name="example",
    )
    base.update(overrides)
    return CompanyDefinition(**base)


# --- Mag7List -------------------------------------------------------------


def test_default_mag7_list_contains_canonical_seven() -> None:
    assert Mag7List.default().members == DEFAULT_MAG7
    assert "apple" in Mag7List.default().members
    assert "nvidia" in Mag7List.default().members


def test_mag7_list_membership_normalizes_case_and_whitespace() -> None:
    m = Mag7List.default()
    assert m.is_mag7("Apple") is True
    assert m.is_mag7("  microsoft  ") is True
    assert m.is_mag7("not_in_list") is False


def test_mag7_list_can_be_injected() -> None:
    custom = Mag7List.from_iterable(["acme", "globex"])
    assert custom.is_mag7("acme") is True
    assert custom.is_mag7("apple") is False


def test_mag7_list_from_iterable_normalizes() -> None:
    m = Mag7List.from_iterable(["  Apple  ", "Microsoft"])
    assert m.members == frozenset({"apple", "microsoft"})


# --- DefaultEligibilityRule -----------------------------------------------


def test_in_scope_sector_yields_eligible_high_confidence() -> None:
    rule = DefaultEligibilityRule()
    result = rule.evaluate(_def(sector_primary="ai"))
    assert result.status is EligibilityStatus.ELIGIBLE
    assert result.confidence is ClassificationConfidence.HIGH_CONFIDENCE
    assert result.score > 0


def test_excluded_sector_yields_ineligible_high_confidence() -> None:
    rule = DefaultEligibilityRule()
    result = rule.evaluate(_def(sector_primary="biotech"))
    assert result.status is EligibilityStatus.INELIGIBLE
    assert result.confidence is ClassificationConfidence.HIGH_CONFIDENCE


def test_missing_sector_yields_ineligible_unknown_confidence() -> None:
    """Honors 'never silently treat unknown as a confident value'."""
    rule = DefaultEligibilityRule()
    result = rule.evaluate(_def(sector_primary=None))
    assert result.status is EligibilityStatus.INELIGIBLE
    assert result.confidence is ClassificationConfidence.UNKNOWN


def test_unrecognized_sector_yields_moderate_confidence() -> None:
    rule = DefaultEligibilityRule()
    result = rule.evaluate(_def(sector_primary="whatever"))
    assert result.status is EligibilityStatus.INELIGIBLE
    assert result.confidence is ClassificationConfidence.MODERATE_CONFIDENCE


def test_default_eligibility_rule_is_deterministic() -> None:
    rule = DefaultEligibilityRule()
    a = rule.evaluate(_def(sector_primary="cloud"))
    b = rule.evaluate(_def(sector_primary="cloud"))
    assert a == b


def test_default_eligibility_rule_normalizes_sector_case() -> None:
    rule = DefaultEligibilityRule()
    result = rule.evaluate(_def(sector_primary="  AI  "))
    assert result.status is EligibilityStatus.ELIGIBLE


# --- DefaultMajorTechRule -------------------------------------------------


def test_default_major_tech_rule_marks_mag7() -> None:
    rule = DefaultMajorTechRule()
    result = rule.evaluate(_def(), is_mag7=True)
    assert result.is_major_tech is True
    assert result.score == 1.0


def test_default_major_tech_rule_does_not_mark_non_mag7() -> None:
    rule = DefaultMajorTechRule()
    result = rule.evaluate(_def(), is_mag7=False)
    assert result.is_major_tech is False
    assert result.score == 0.0


def test_default_major_tech_rule_is_deterministic() -> None:
    rule = DefaultMajorTechRule()
    a = rule.evaluate(_def(), is_mag7=True)
    b = rule.evaluate(_def(), is_mag7=True)
    assert a == b
