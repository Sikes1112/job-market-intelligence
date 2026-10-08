"""Slice 18 integration test — full MVP demo path.

Verifies that the deterministic seed dataset can drive the entire MVP
read surface end-to-end, that re-running the seed flow does not duplicate
logical rows, and that no external network/scraping/AI clients leak into
the seed code path.
"""

from __future__ import annotations

import importlib
import pathlib
import sys
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.api.app import create_app
from backend.api.dependencies import get_session
from backend.companies.models import Company
from backend.companies.types import EligibilityStatus
from backend.entry_level.models import CompanyRegionEntryLevel
from backend.geography.models import Region, RegionAlias, RegionStateMembership
from backend.hiring.models import CompanyRegionHiring
from backend.outputs.models import OutputMetadata
from backend.outputs.types import OutputType
from backend.presence.models import CompanyRegionPresence
from backend.provenance.models import FactSourceLink, SourceObservation, SourceRef
from backend.scoring.models import RegionMarketScore
from backend.shared.provenance import DataOrigin, FactBindingType
from seeds import mvp_seed
from seeds.mvp_data import (
    COMPANIES,
    ENTRY_LEVEL,
    HIRING,
    PRESENCE,
    REGION_BOSTON,
    REGION_SF,
    REGIONS,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def seeded_session(session: Session) -> Session:
    """The shared in-memory ``session`` fixture seeded with the demo data."""
    mvp_seed.run_seed(session)
    session.commit()
    return session


@pytest.fixture
def seeded_client(seeded_session: Session) -> TestClient:
    app = create_app(engine=seeded_session.bind)

    def _override() -> Iterator[Session]:
        yield seeded_session

    app.dependency_overrides[get_session] = _override
    return TestClient(app)


# ---------------------------------------------------------------------------
# Canonical-truth assertions
# ---------------------------------------------------------------------------


def test_seed_creates_both_regions(seeded_session: Session) -> None:
    rows = seeded_session.query(Region).order_by(Region.region_id).all()
    region_ids = {r.region_id for r in rows}
    assert region_ids == {REGION_BOSTON, REGION_SF}
    for r in rows:
        assert r.state == "fresh"
        assert r.public_slug
        assert r.market_support_status == "supported"
    sf_aliases = {
        row.normalized_alias
        for row in seeded_session.query(RegionAlias).filter_by(region_id=REGION_SF)
    }
    assert {"greater sf", "san francisco bay area", "san francisco"}.issubset(
        sf_aliases
    )
    assert seeded_session.get(RegionStateMembership, (REGION_BOSTON, "MA")) is not None
    assert seeded_session.get(RegionStateMembership, (REGION_SF, "CA")) is not None
    assert seeded_session.get(Region, "greater_sf") is None


def test_seed_creates_companies(seeded_session: Session) -> None:
    rows = seeded_session.query(Company).all()
    company_ids = {c.company_id for c in rows}
    expected = {c.company_id for c in COMPANIES}
    assert expected == company_ids

    by_id = {c.company_id: c for c in rows}
    # Mag 7 is detected by the default classifier.
    assert by_id["comp_alphabet"].is_mag7 is True
    assert by_id["comp_alphabet"].is_major_tech is True
    assert by_id["comp_microsoft"].is_mag7 is True
    assert by_id["comp_meta"].is_mag7 is True
    # Override path:
    assert (
        by_id["comp_specialized_ai"].eligibility_status
        == EligibilityStatus.OVERRIDE_INCLUDED.value
    )
    assert by_id["comp_specialized_ai"].eligibility_override_flag is True
    # Ineligible (biotech is on the documented exclusion list).
    assert (
        by_id["comp_biotech_research"].eligibility_status
        == EligibilityStatus.INELIGIBLE.value
    )
    # Plain eligible mid-market firms.
    assert by_id["comp_hubspot"].eligibility_status == EligibilityStatus.ELIGIBLE.value
    assert by_id["comp_databricks"].eligibility_status == EligibilityStatus.ELIGIBLE.value


def test_seed_creates_presence_records(seeded_session: Session) -> None:
    rows = seeded_session.query(CompanyRegionPresence).all()
    assert len(rows) == len(PRESENCE)

    bases = {r.presence_basis for r in rows}
    # Every documented basis path the seed exercises must show up.
    assert "office_plus_hiring" in bases
    assert "office_plus_operations" in bases
    assert "satellite_office_only" in bases

    # All seeded presence records should be present (not uncertain) since
    # allow_satellite_office_presence defaults to True.
    statuses = {r.presence_status for r in rows}
    assert statuses == {"present"}


def test_seed_creates_hiring_records(seeded_session: Session) -> None:
    rows = seeded_session.query(CompanyRegionHiring).all()
    assert len(rows) == len(HIRING)

    flags = {r.currently_hiring_flag for r in rows}
    assert flags == {True, False}

    # Active posting / 30d / 90d windows must be populated for hiring rows
    # the seed declared currently_hiring=True.
    hiring_rows = [r for r in rows if r.currently_hiring_flag]
    assert all(
        r.active_posting_count_now is not None
        and r.posting_count_30d is not None
        and r.posting_count_90d is not None
        for r in hiring_rows
    )

    role_keys: set[str] = set()
    for r in rows:
        if r.role_family_summary:
            role_keys.update(r.role_family_summary.keys())
    assert {"product", "ai_cloud_adjacent", "cybersecurity"}.issubset(role_keys)


def test_seed_creates_entry_level_records(seeded_session: Session) -> None:
    rows = seeded_session.query(CompanyRegionEntryLevel).all()
    assert len(rows) == len(ENTRY_LEVEL)

    has_internships = any((r.internship_count or 0) > 0 for r in rows)
    has_coops = any((r.coop_count or 0) > 0 for r in rows)
    has_full_time = any((r.entry_level_full_time_count or 0) > 0 for r in rows)
    has_formal = any(r.formal_early_career_program_flag for r in rows)
    has_recurrence = any(r.student_season_recurrence_signal is not None for r in rows)
    has_score = any((r.entry_level_access_score or 0) > 0 for r in rows)
    assert has_internships
    assert has_coops
    assert has_full_time
    assert has_formal
    assert has_recurrence
    assert has_score


def test_seed_creates_region_scores(seeded_session: Session) -> None:
    rows = seeded_session.query(RegionMarketScore).all()
    assert {r.region_id for r in rows} == {REGION_BOSTON, REGION_SF}
    for r in rows:
        # Region scores are written via the upsert flow, which walks
        # new → building → fresh on first build.
        assert r.state == "fresh"
        assert r.objective_opportunity_score is not None
        assert r.early_career_accessibility_score is not None


def test_seed_labels_demo_provenance(seeded_session: Session) -> None:
    source_ref = seeded_session.get(SourceRef, "mvp_demo_seed")
    observation = seeded_session.get(
        SourceObservation,
        "mvp_demo_seed_observation",
    )
    links = seeded_session.query(FactSourceLink).all()

    assert source_ref is not None
    assert source_ref.data_origin == DataOrigin.DEMO_SEED.value
    assert "not factual public market coverage" in (source_ref.notes or "")

    assert observation is not None
    assert observation.data_origin == DataOrigin.SYNTHETIC_OR_CURATED_DEMO.value
    assert "not factual public market coverage" in (observation.notes or "")

    expected_count = (
        len(REGIONS)
        + len(COMPANIES)
        + len(PRESENCE)
        + len(HIRING)
        + len(ENTRY_LEVEL)
        + len(REGIONS)
    )
    assert len(links) == expected_count
    assert {link.data_origin for link in links} == {DataOrigin.DEMO_SEED.value}
    assert {link.fact_type for link in links} == {
        FactBindingType.COMPANY.value,
        FactBindingType.REGION.value,
        FactBindingType.COMPANY_REGION_PRESENCE.value,
        FactBindingType.COMPANY_REGION_HIRING.value,
        FactBindingType.COMPANY_REGION_ENTRY_LEVEL.value,
        FactBindingType.SCORE_INPUT.value,
    }
    assert all("not factual public market coverage" in (link.notes or "") for link in links)


def test_seed_creates_output_metadata(seeded_session: Session) -> None:
    rows = seeded_session.query(OutputMetadata).all()
    pairs = {(r.output_type, r.subject_id) for r in rows}

    # Region outputs.
    assert (OutputType.REGION_OUTPUT.value, REGION_BOSTON) in pairs
    assert (OutputType.REGION_OUTPUT.value, REGION_SF) in pairs
    # One company output per seeded company.
    for definition in COMPANIES:
        assert (OutputType.COMPANY_OUTPUT.value, definition.company_id) in pairs
    # Comparison + contextual challenge outputs (canonical sorted pair id).
    canonical_pair = f"{REGION_BOSTON}__{REGION_SF}"
    assert (OutputType.COMPARISON_OUTPUT.value, canonical_pair) in pairs
    assert (
        OutputType.CONTEXTUAL_CHALLENGE_OUTPUT.value,
        canonical_pair,
    ) in pairs


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


def test_run_seed_is_idempotent(session: Session) -> None:
    first = mvp_seed.run_seed(session)
    session.commit()
    second = mvp_seed.run_seed(session)
    session.commit()

    # First run creates everything.
    assert first.regions["created"] == len(REGIONS)
    assert first.companies["created"] == len(COMPANIES)
    assert first.presence["created"] == len(PRESENCE)
    assert first.hiring["created"] == len(HIRING)
    assert first.entry_level["created"] == len(ENTRY_LEVEL)

    # Second run must not create or update any logical rows — every layer
    # should be reported as ``unchanged``.
    for label, counter in (
        ("regions", second.regions),
        ("companies", second.companies),
        ("presence", second.presence),
        ("hiring", second.hiring),
        ("entry_level", second.entry_level),
        ("region_scores", second.region_scores),
        ("region_outputs", second.region_outputs),
        ("company_outputs", second.company_outputs),
        ("comparison_outputs", second.comparison_outputs),
        ("contextual_outputs", second.contextual_outputs),
    ):
        assert counter.get("created", 0) == 0, f"{label}: unexpected creates"
        assert counter.get("updated", 0) == 0, f"{label}: unexpected updates"

    assert second.regions["unchanged"] == len(REGIONS)
    assert second.companies["unchanged"] == len(COMPANIES)
    assert second.presence["unchanged"] == len(PRESENCE)
    assert second.hiring["unchanged"] == len(HIRING)
    assert second.entry_level["unchanged"] == len(ENTRY_LEVEL)

    # Row counts in canonical tables match the seed sizes (no duplication).
    assert session.query(Region).count() == len(REGIONS)
    assert session.query(Company).count() == len(COMPANIES)
    assert session.query(CompanyRegionPresence).count() == len(PRESENCE)
    assert session.query(CompanyRegionHiring).count() == len(HIRING)
    assert session.query(CompanyRegionEntryLevel).count() == len(ENTRY_LEVEL)
    assert session.query(RegionMarketScore).count() == len(REGIONS)
    assert session.query(SourceRef).count() == 1
    assert session.query(SourceObservation).count() == 1
    assert session.query(FactSourceLink).count() == (
        len(REGIONS)
        + len(COMPANIES)
        + len(PRESENCE)
        + len(HIRING)
        + len(ENTRY_LEVEL)
        + len(REGIONS)
    )


# ---------------------------------------------------------------------------
# API read paths against the seeded DB
# ---------------------------------------------------------------------------


def test_get_regions_returns_seed_regions(seeded_client: TestClient) -> None:
    resp = seeded_client.get("/regions")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "success"
    region_ids = {r["region_id"] for r in body["data"]["regions"]}
    assert region_ids == {REGION_BOSTON, REGION_SF}


def test_get_region_detail(seeded_client: TestClient) -> None:
    resp = seeded_client.get(f"/regions/{REGION_BOSTON}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] in ("success", "partial")
    region = body["data"]
    assert region["region_id"] == REGION_BOSTON
    assert region["scores"] is not None


def test_get_company_detail(seeded_client: TestClient) -> None:
    resp = seeded_client.get("/companies/comp_alphabet")
    assert resp.status_code == 200
    body = resp.json()
    company = body["data"]
    assert company["company_id"] == "comp_alphabet"
    assert company["is_mag7"] is True


def test_get_comparison(seeded_client: TestClient) -> None:
    resp = seeded_client.get(
        "/compare", params={"region_a": REGION_BOSTON, "region_b": REGION_SF}
    )
    assert resp.status_code == 200
    body = resp.json()
    comparison = body["data"]
    assert comparison["comparison_id"] == f"{REGION_BOSTON}__{REGION_SF}"


def test_post_personalized_discovery(seeded_client: TestClient) -> None:
    payload = {
        "role_targets": ["product", "ai_cloud_adjacent"],
        "industry_preferences": ["ai", "cloud", "data"],
        "career_stage": "entry_level",
        "prestige_preference": "medium",
        "brand_preference": "medium",
        "region_ids": [REGION_BOSTON, REGION_SF],
        "limit": 25,
    }
    resp = seeded_client.post("/discover/personalized", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    personalized = body["data"]

    region_ids = {r["region_id"] for r in personalized["ranked_regions"]}
    assert region_ids == {REGION_BOSTON, REGION_SF}

    company_ids = {c["company_id"] for c in personalized["ranked_companies"]}
    assert "comp_alphabet" in company_ids


# ---------------------------------------------------------------------------
# Guardrails — no external clients in the seed/demo path
# ---------------------------------------------------------------------------


# Modules whose presence in :data:`sys.modules` after importing the seed
# code would indicate scraping / NLP / ML / external HTTP leakage. ``httpx``
# is *not* listed here because FastAPI's TestClient (used elsewhere in the
# test suite) imports it transitively; the static check below verifies the
# seed source files themselves do not name it.
_FORBIDDEN_RUNTIME_MODULES = {
    "requests",
    "selenium",
    "playwright",
    "bs4",
    "scrapy",
    "openai",
    "anthropic",
    "transformers",
    "torch",
    "tensorflow",
    "spacy",
    "nltk",
}


def test_no_external_clients_imported() -> None:
    """Importing the seed modules must not pull in forbidden clients."""
    importlib.import_module("seeds.mvp_data")
    importlib.import_module("seeds.mvp_seed")
    leaked = _FORBIDDEN_RUNTIME_MODULES & set(sys.modules.keys())
    assert leaked == set(), f"forbidden modules imported: {sorted(leaked)}"


def test_seed_sources_have_no_forbidden_imports() -> None:
    """Static check: the seed/demo files do not name forbidden clients."""
    forbidden_substrings = (
        "import requests",
        "import httpx",
        "import selenium",
        "import playwright",
        "import bs4",
        "import scrapy",
        "import openai",
        "import anthropic",
        "import transformers",
        "import torch",
        "import tensorflow",
        "import spacy",
        "import nltk",
        "from requests",
        "from httpx",
        "from selenium",
        "from playwright",
        "from bs4",
        "from scrapy",
        "from openai",
        "from anthropic",
        "from transformers",
        "from torch",
        "from tensorflow",
        "from spacy",
        "from nltk",
    )
    repo_root = pathlib.Path(__file__).resolve().parents[2]
    for relpath in (
        "seeds/__init__.py",
        "seeds/mvp_data.py",
        "seeds/mvp_seed.py",
        "scripts/seed_demo.py",
    ):
        text = (repo_root / relpath).read_text(encoding="utf-8")
        for needle in forbidden_substrings:
            assert needle not in text, (
                f"{relpath} imports forbidden module fragment: {needle!r}"
            )
