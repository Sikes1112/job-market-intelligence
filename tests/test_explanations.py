from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError
from sqlalchemy.orm import Session

from backend.explanations.payloads import (
    ExplanationEntityType,
    ExplanationEvidencePacket,
    FreshnessEvidence,
    ScoringFactorEvidence,
)
from backend.explanations.service import ExplanationService
from backend.geography.models import Region
from backend.scoring.models import RegionMarketScore

_NOW = datetime(2026, 5, 25, 14, tzinfo=UTC)


def _auth_headers(subject: str = "auth0|explanation_user") -> dict[str, str]:
    suffix = subject.split("|")[-1]
    return {
        "X-Verified-OIDC-Claims": json.dumps(
            {
                "iss": "https://jmi.us.auth0.com/",
                "sub": subject,
                "email": f"{suffix}@example.com",
                "email_verified": True,
                "name": f"User {suffix}",
            }
        )
    }


def _region_packet(**overrides) -> ExplanationEvidencePacket:
    values = {
        "entity_type": ExplanationEntityType.REGION,
        "subject_refs": {"region_id": "greater_boston"},
        "display_label": "Greater Boston",
        "canonical_scores": {
            "objective_opportunity_score": 0.74,
            "early_career_accessibility_score": 0.68,
        },
        "personalized_overlay": {"personalized_overlay_score": 0.81},
        "scoring_factors": [
            ScoringFactorEvidence(
                factor="entry_level_access",
                label="Entry-level access",
                value=0.68,
                weight=0.4,
                status="used",
            )
        ],
        "freshness": FreshnessEvidence(
            freshness_status="fresh",
            data_basis="real_imported",
            freshness_expires_at="2026-06-25T14:00:00+00:00",
            source_count=2,
        ),
        "source_refs": ["region_market_scores:score_boston:v1"],
    }
    values.update(overrides)
    return ExplanationEvidencePacket(**values)


def test_explanation_packet_validation_rejects_empty_or_unsafe_evidence() -> None:
    with pytest.raises(ValidationError):
        ExplanationEvidencePacket(entity_type=ExplanationEntityType.REGION)

    with pytest.raises(ValidationError):
        _region_packet(canonical_scores={"raw_payload_score": 0.4})

    with pytest.raises(ValidationError):
        _region_packet(canonical_scores={"objective_opportunity_score": 4.0})


@pytest.mark.parametrize(
    "unsafe_key",
    [
        "score",
        "scores",
        "canonical_score",
        "personalized_score",
        "freshness",
        "provenance",
        "sources",
        "source_summary",
        "evidence",
        "companies",
        "regions",
        "market_output",
        "output",
        "hiring",
        "entry_level_signal",
        "company_detail",
        "region_detail",
    ],
)
def test_explanation_packet_rejects_copied_market_payload_keys(
    unsafe_key: str,
) -> None:
    with pytest.raises(ValidationError):
        _region_packet(subject_refs={"region_id": "greater_boston", unsafe_key: "copied"})

    with pytest.raises(ValidationError):
        _region_packet(canonical_scores={unsafe_key: 0.4})


def test_explanation_renderer_uses_only_structured_packet_fields() -> None:
    result = ExplanationService().explain(_region_packet())

    rendered = json.dumps(result.model_dump(mode="json"))
    assert result.provider_mode == "deterministic_structured_guidance"
    assert result.status == "ok"
    assert "Canonical/default score fields present" in rendered
    assert "Personalized overlay fields are separate" in rendered
    assert "Entry-level access 68% at 40% weight" in rendered
    assert "internship" not in rendered.lower()


def test_explanation_constrains_output_for_missing_stale_or_unsupported_evidence() -> None:
    packet = _region_packet(
        freshness=FreshnessEvidence(
            freshness_status="stale",
            data_basis="seeded_demo",
            source_count=0,
        ),
        demo_or_seeded=True,
        missing_data=["source coverage"],
        unsupported_data=["historical trend", "map geometry"],
    )

    result = ExplanationService().explain(packet)
    rendered = json.dumps(result.model_dump(mode="json"))

    assert result.status == "constrained"
    assert "seeded/demo" in rendered
    assert "historical trend" in rendered
    assert "Unsupported dimensions are not inferred" in rendered


def test_protected_explanation_route_requires_auth_and_does_not_mutate_market_rows(
    api_client,
    session: Session,
) -> None:
    session.add(
        Region(
            region_id="greater_boston",
            region_name="greater_boston",
            display_name="Greater Boston",
            region_type="greater_region",
        )
    )
    session.flush()
    session.add(
        RegionMarketScore(
            region_score_id="score_boston",
            region_id="greater_boston",
            objective_opportunity_score=0.74,
            score_ruleset_version="marketscore_v1",
            created_at=_NOW,
        )
    )
    session.flush()
    before_version = session.get(RegionMarketScore, "score_boston").version
    payload = {"evidence": _region_packet().model_dump(mode="json")}

    unauthenticated = api_client.post("/me/explanations/region", json=payload)
    assert unauthenticated.status_code == 401

    response = api_client.post(
        "/me/explanations/region",
        headers=_auth_headers(),
        json=payload,
    )

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["provider_mode"] == "deterministic_structured_guidance"
    assert body["entity_type"] == "region"
    assert session.get(RegionMarketScore, "score_boston").version == before_version


def test_explanation_route_rejects_entity_type_mismatch(api_client) -> None:
    response = api_client.post(
        "/me/explanations/company",
        headers=_auth_headers(),
        json={"evidence": _region_packet().model_dump(mode="json")},
    )

    assert response.status_code == 400
    assert "entity_type='company'" in response.json()["error"]["message"]
