# API Surfaces

This file documents the MVP API surface that is currently implemented. It is intentionally narrow: the local demo reads seeded backend data and does not expose auth, accounts, scraping, admin tooling, maps, or production deployment controls. Current status is an internal-production baseline for local/single-process operation, not external-production readiness.

## Response Envelope

Most successful responses use:

```json
{
  "status": "success",
  "data": {},
  "metadata": {
    "state": "fresh",
    "freshness": {
      "last_updated_at": "ISO-8601 timestamp or null",
      "freshness_expires_at": "ISO-8601 timestamp or null",
      "is_stale": false,
      "freshness_status": "fresh | stale | unknown"
    },
    "source_versions": {},
    "warnings": []
  },
  "error": null
}
```

Lightweight endpoints may omit `freshness` and `source_versions` from `metadata`. When `freshness_expires_at` is `null`, `freshness_status` is `unknown`; do not interpret `is_stale: false` by itself as proof of tracked freshness.

Errors use:

```json
{
  "status": "error",
  "data": null,
  "metadata": {
    "state": "failed",
    "warnings": []
  },
  "error": {
    "code": "NOT_FOUND",
    "message": "Region not found."
  }
}
```

Warnings are structured objects when available:

```json
{
  "warning_code": "region_score_missing",
  "severity": "medium",
  "message": "no region_market_scores row for 'greater_boston'",
  "scope_type": "region",
  "scope_ref": "greater_boston"
}
```

## Implemented Public Endpoints

For the local MVP, full output endpoints assemble response payloads on read through the output assembly service without creating or updating `OutputMetadata` cache metadata. They do not run foundational ingestion, external refreshes, scraping, or scoring recomputation during request handling.

### `GET /health`

Basic health check. It does not touch the database.

Response `data`:

```json
{
  "service": "ok"
}
```

### `GET /regions`

Lightweight region list. This reads region identity rows only and does not return full region output sections.

Response `data`:

```json
{
  "regions": [
    {
      "region_id": "greater_boston",
      "display_name": "Greater Boston",
      "region_type": "greater_region",
      "parent_region_id": null,
      "labor_market_group": "boston_labor_market",
      "state": "fresh",
      "version": 1
    }
  ]
}
```

### `GET /regions/{region_id}`

Returns the assembled region output in a flattened `data` body. The response does not wrap the body in a `region` key.

Response `data`:

```json
{
  "region_id": "greater_boston",
  "display_name": "Greater Boston",
  "region_type": "greater_region",
  "parent_region_id": null,
  "labor_market_group": "boston_labor_market",
  "summary": {
    "eligible_company_count": 6,
    "major_tech_count": 2,
    "mag7_count": 2,
    "present_company_count": 5,
    "currently_hiring_company_count": 4
  },
  "scores": {
    "structural_ecosystem_score": 0.72,
    "live_market_score": 0.68,
    "objective_opportunity_score": 0.74,
    "raw_total_score": 0.71,
    "general_density_score": 0.76,
    "tech_market_density_score": 0.73,
    "early_career_accessibility_score": 0.79,
    "score_ruleset_version": "marketscore_v1"
  },
  "top_companies_present": [],
  "top_companies_hiring": [],
  "entry_level_summary": {
    "internship_count_total": 25,
    "coop_count_total": 15,
    "entry_level_full_time_count_total": 28,
    "formal_early_career_program_count": 2,
    "average_entry_level_access_score": 0.71,
    "pairs_with_entry_level_access": 5
  },
  "major_tech_summary": {
    "count": 2,
    "company_ids": ["comp_alphabet", "comp_microsoft"]
  },
  "mag7_summary": {
    "count": 2,
    "company_ids": ["comp_alphabet", "comp_microsoft"]
  }
}
```

### `GET /companies/{company_id}`

Returns the assembled company output in a flattened `data` body. The response does not wrap the body in a `company` key.

Response `data`:

```json
{
  "company_id": "comp_alphabet",
  "company_name": "Alphabet",
  "normalized_company_name": "alphabet",
  "sector_primary": "ai",
  "sector_secondary": "cloud",
  "eligibility_status": "eligible",
  "eligibility_override_flag": false,
  "classification_confidence": "high_confidence",
  "is_major_tech": true,
  "is_mag7": true,
  "prestige_score": 0.95,
  "regions_present": [],
  "regions_hiring": [],
  "entry_level_regions": []
}
```

### `GET /compare`

Query parameters:

- `region_a`: required region id
- `region_b`: required region id

Returns the comparison output in a flattened `data` body. The backend canonicalizes comparison ordering by region id, so `region_a` and `region_b` in the response may be sorted rather than matching request order.

Response `data`:

```json
{
  "comparison_id": "greater_boston__greater_sf",
  "region_a": {
    "region_id": "greater_boston",
    "display_name": "Greater Boston",
    "scores": {}
  },
  "region_b": {
    "region_id": "greater_sf",
    "display_name": "Greater San Francisco / Silicon Valley",
    "scores": {}
  },
  "category_winners": {
    "structural_ecosystem_score": "greater_sf",
    "early_career_accessibility_score": "greater_boston",
    "objective_opportunity_score": "greater_boston"
  },
  "notes": []
}
```

`category_winners` maps score field name to winning `region_id`. A value of `null` means an honest tie. Categories with missing score values are omitted.

### `POST /discover/personalized`

Request body:

```json
{
  "role_targets": ["product", "ai_cloud_adjacent"],
  "industry_preferences": ["ai", "cloud"],
  "career_stage": "entry_level",
  "prestige_preference": "medium",
  "brand_preference": "medium",
  "region_ids": ["greater_boston", "greater_sf"],
  "limit": 25
}
```

Returns the implemented personalized payload in a flattened `data` body. The response does not wrap the body in a `personalized` key. Preferences are request-scoped and are not persisted.

Response `data`:

```json
{
  "ranked_regions": [
    {
      "region_id": "greater_boston",
      "display_name": "Greater Boston",
      "personal_market_score": 0.78,
      "objective_opportunity_score": 0.74,
      "match_notes": []
    }
  ],
  "ranked_companies": [
    {
      "company_id": "comp_alphabet",
      "company_name": "Alphabet",
      "region_id": "greater_boston",
      "region_display_name": "Greater Boston",
      "personal_company_score": 0.84,
      "role_fit": 0.75,
      "industry_fit": 1.0,
      "prestige_fit": 0.9,
      "brand_fit": 1.0,
      "match_notes": []
    }
  ]
}
```

## Deferred Endpoints

These endpoints may appear in older planning docs, but they are not currently implemented as public API routes:

- `GET /regions/{region_id}/companies`
- `GET /regions/{region_id}/hiring`
- `GET /regions/{region_id}/entry-level`
- `GET /companies/{company_id}/regions`
- `GET /companies/{company_id}/hiring`
- `GET /compare/contextual`
- `GET /search/companies`
- `GET /search/regions`
- `POST /admin/jobs/run`
- `POST /admin/refresh/region`
- `POST /admin/refresh/company`

The contextual challenge builder and seed path exist in backend code, but there is no public `GET /compare/contextual` endpoint in the current MVP.

## Runtime And Orchestration Boundaries

- Full output GET endpoints assemble response payloads in read-only mode. They do not create or update `OutputMetadata`; seed flows and output-build job handlers are responsible for cache metadata writes.
- Event invalidation returns directives/recommendations and can apply a narrow stale-marking pass for existing `OutputMetadata` rows affected by region/company/comparison output directives. Stale marking requires the DB-session-backed dispatch path; dispatch without a session reports stale marking as skipped. It does not delete rows, rebuild outputs, enqueue jobs beyond existing routing behavior, or run workers.
- Scheduler-generated `dependency_refs` are still opaque by default. The runtime also supports optional DB-backed refs in the form `kind:object_id@vN` through an injected database dependency resolver; there is no full source-version dependency graph.
- Queue dedupe uses an application-level check plus a partial unique index for active `dedupe_key` rows on SQLite/PostgreSQL. This is DB-level protection for supported databases, not a replacement for a production broker, distributed lock, or multi-worker orchestration.
- Audit and contextual challenge handlers/services exist for backend use, but they are not registered in the default worker registry and are not exposed as public API routes.

External-production work remains deferred: migrations, deployment configuration, auth/security, observability, distributed queue/broker integration, artifact storage/cache serving, and multi-worker stress testing.

## MVP Non-Goals

Do not implement unless explicitly requested:

- authentication-heavy user account systems
- saved profiles or application tracking
- scraping or external APIs
- maps or advanced charts
- production deployment/security controls
- public mutation APIs for canonical truth
- persistent personalized outputs
