from __future__ import annotations

import json

from sqlalchemy.orm import Session

from backend.companies.models import Company
from backend.entry_level.models import CompanyRegionEntryLevel
from backend.geography.models import Region
from backend.hiring.models import CompanyRegionHiring
from backend.presence.models import CompanyRegionPresence
from backend.scoring.models import RegionMarketScore


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


def _current_user_id(api_client, subject: str) -> tuple[dict[str, str], str]:
    headers = _auth_headers(subject)
    response = api_client.get("/me", headers=headers)
    assert response.status_code == 200
    return headers, response.json()["data"]["user"]["user_id"]


def _seed_market(session: Session) -> None:
    session.add(
        Region(
            region_id="greater_boston",
            region_name="greater_boston",
            display_name="Greater Boston",
            region_type="greater_region",
        )
    )
    session.add(
        Company(
            company_id="comp_alpha",
            company_name="Alpha Systems",
            normalized_company_name="alpha systems",
            sector_primary="software",
            eligibility_status="eligible",
            classification_confidence="high",
            prestige_score=0.71,
        )
    )
    session.flush()
    session.add_all(
        [
            CompanyRegionPresence(
                presence_id="presence_alpha_boston",
                company_id="comp_alpha",
                region_id="greater_boston",
                presence_status="present",
                presence_basis="office_plus_hiring",
                office_evidence_flag=True,
                hiring_evidence_flag=True,
                presence_confidence="high",
            ),
            CompanyRegionHiring(
                hiring_id="hiring_alpha_boston",
                company_id="comp_alpha",
                region_id="greater_boston",
                currently_hiring_flag=True,
                active_posting_count_now=12,
                posting_count_30d=18,
                posting_count_90d=42,
                hiring_confidence="high",
            ),
            CompanyRegionEntryLevel(
                entry_level_id="entry_alpha_boston",
                company_id="comp_alpha",
                region_id="greater_boston",
                internship_count=4,
                coop_count=2,
                entry_level_full_time_count=5,
                formal_early_career_program_flag=True,
                entry_level_access_score=0.82,
                entry_level_confidence="high",
            ),
            RegionMarketScore(
                region_score_id="score_boston",
                region_id="greater_boston",
                structural_ecosystem_score=0.73,
                live_market_score=0.68,
                objective_opportunity_score=0.81,
                raw_total_score=0.77,
                general_density_score=0.7,
                tech_market_density_score=0.72,
                early_career_accessibility_score=0.86,
                score_ruleset_version="internal_ruleset_v1",
            ),
        ]
    )
    session.flush()


def _create_export(api_client, headers: dict[str, str], export_format: str):
    return api_client.post(
        "/api/integrations/exports",
        headers=headers,
        json={
            "product_object_type": "region",
            "product_object_id": "greater_boston",
            "export_format": export_format,
        },
    )


def test_csv_export_includes_provenance_freshness_and_confidence_metadata(
    api_client,
    session: Session,
) -> None:
    _seed_market(session)
    headers, _ = _current_user_id(api_client, "auth0|csv_export_user")

    created = _create_export(api_client, headers, "csv")

    assert created.status_code == 201
    export = created.json()["data"]["export"]
    assert export["receipt"]["external_write_performed"] is False
    assert export["receipt"]["live_sync_enabled"] is False
    assert export["receipt"]["provenance"]["product_object_type"] == "region"
    assert export["receipt"]["provenance"]["freshness_status"] in {"fresh", "partial"}
    assert export["receipt"]["provenance"]["confidence_label"]

    downloaded = api_client.get(
        f"/api/integrations/exports/{export['export_id']}/download",
        headers=headers,
    )
    assert downloaded.status_code == 200
    assert downloaded.headers["content-type"].startswith("text/csv")
    text = downloaded.text
    assert "provenance,product_object_type,region" in text
    assert "freshness,freshness_status" in text
    assert "confidence,confidence_label" in text
    assert "governance,live_sync_enabled,false" in text


def test_pdf_export_includes_limitations_and_governance_warnings(
    api_client,
    session: Session,
) -> None:
    _seed_market(session)
    headers, _ = _current_user_id(api_client, "auth0|pdf_export_user")

    created = _create_export(api_client, headers, "pdf")

    assert created.status_code == 201
    export = created.json()["data"]["export"]
    assert export["content_type"] == "application/pdf"
    assert export["payload"]["limitations"]
    assert export["payload"]["governance_warnings"]
    receipt_text = json.dumps(export["receipt"])
    assert "No OAuth" not in receipt_text
    assert "External destinations must not be treated as product authority" in receipt_text

    downloaded = api_client.get(
        f"/api/integrations/exports/{export['export_id']}/download",
        headers=headers,
    )
    assert downloaded.status_code == 200
    assert downloaded.content.startswith(b"%PDF-1.4")
    assert b"Limitations and governance warnings" in downloaded.content


def test_prepared_external_payloads_do_not_imply_live_sync(api_client, session: Session) -> None:
    _seed_market(session)
    headers, _ = _current_user_id(api_client, "auth0|prepared_export_user")

    for export_format, payload_key in {
        "prepared_google_sheets": "prepared_google_sheets_payload",
        "prepared_notion": "prepared_notion_payload",
        "prepared_airtable": "prepared_airtable_payload",
    }.items():
        created = _create_export(api_client, headers, export_format)
        assert created.status_code == 201
        export = created.json()["data"]["export"]
        payload = export["payload"]
        assert payload[payload_key]
        assert payload["mode"] == "prepared_manual_payload"
        assert payload["operation"] == "manual_copy_only"
        assert payload["sync_mode"] == "none"
        assert payload["external_write_performed"] is False
        assert payload["live_sync_enabled"] is False
        assert payload["two_way_sync_enabled"] is False
        assert payload["oauth_required"] is False
        assert export["receipt"]["risk_posture"] == "prepared_no_sync"


def test_internal_only_scoring_and_source_fields_are_not_exported(
    api_client,
    session: Session,
) -> None:
    _seed_market(session)
    headers, _ = _current_user_id(api_client, "auth0|safe_export_user")

    created = _create_export(api_client, headers, "csv")
    export = created.json()["data"]["export"]
    downloaded = api_client.get(
        f"/api/integrations/exports/{export['export_id']}/download",
        headers=headers,
    )

    text = downloaded.text
    assert "raw_total_score" not in text
    assert "score_ruleset_version" not in text
    assert "internal_ruleset_v1" not in text
    assert "source_versions" not in text
    assert "source_ref_id" not in text
