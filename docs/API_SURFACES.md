# API_SURFACES.md

## Purpose

This file defines the MVP API surface for the job-market intelligence platform backend.

It exists to prevent endpoint drift during implementation.

Claude Code must treat this file as the source of truth for MVP API boundaries unless a later prompt explicitly updates it.

---

## API Design Principle

The API layer should be thin.

Public/user-facing endpoints should mostly:

1. read prepared canonical or derived objects
2. apply lightweight filters/sorting where appropriate
3. return state/freshness metadata
4. avoid heavy truth-building work during request time

Do not put orchestration-heavy logic inside route handlers.

---

## Layer Separation Rule

The API must preserve the system’s three-layer structure:

### 1. Canonical market truth
Examples:
- companies
- regions
- company-region presence
- hiring
- entry-level records
- region scores

### 2. Derived app outputs
Examples:
- region output object
- company output object
- comparison output object

### 3. User-specific overlays
Examples:
- personalized rankings
- personalized company targets
- role/industry filtered views

Public APIs may read from all three, but must not collapse them into one mutable object.

---

# 1. API Categories

MVP V1 should include these API categories:

1. Health / system status
2. Region read APIs
3. Company read APIs
4. Comparison APIs
5. Search/filter APIs
6. Personalized discovery APIs
7. Minimal admin/internal refresh APIs

---

# 2. General Response Envelope

All API responses should follow a consistent shape where practical.

```json
{
  "status": "success | partial | error",
  "data": {},
  "metadata": {
    "state": "fresh | stale | partial | failed | blocked | rebuilding | unknown",
    "freshness": {
      "last_updated_at": "ISO-8601 timestamp or null",
      "freshness_expires_at": "ISO-8601 timestamp or null",
      "is_stale": false
    },
    "source_versions": {},
    "warnings": []
  },
  "error": null
}
For errors:
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

⸻

3. Health Endpoints
GET /health
Purpose
Basic backend health check.
Request
No body.
Response
{
  "status": "success",
  "data": {
    "service": "ok"
  },
  "metadata": {
    "state": "fresh",
    "warnings": []
  },
  "error": null
}
Scope
In MVP, this can be simple.
Must not do
* run DB migrations
* trigger refresh jobs
* perform heavy dependency checks

⸻

4. Region APIs
GET /regions
Purpose
Return supported regions.
Query params
Optional:
* region_type
* parent_region_id
* labor_market_group
Response data
{
  "regions": [
    {
      "region_id": "greater_boston",
      "display_name": "Greater Boston",
      "region_type": "greater_region",
      "parent_region_id": "massachusetts",
      "labor_market_group": "boston_labor_market",
      "state": "fresh"
    }
  ]
}
Reads from
* regions
Must not do
* build new region objects
* infer custom geographies live

⸻

GET /regions/{region_id}
Purpose
Return the assembled region output object if available.
This is the main region page endpoint.
Response data
{
  "region": {
    "region_id": "greater_boston",
    "display_name": "Greater Boston",
    "summary": {},
    "scores": {
      "structural_ecosystem_score": 0.72,
      "live_market_score": 0.68,
      "objective_opportunity_score": 0.74,
      "raw_total_score": 0.71,
      "general_density_score": 0.76,
      "tech_market_density_score": 0.73,
      "early_career_accessibility_score": 0.79
    },
    "top_companies_present": [],
    "top_companies_hiring": [],
    "entry_level_summary": {},
    "major_tech_summary": {},
    "mag7_summary": {}
  }
}
Reads from
Preferred:
* region_outputs
Fallback:
* regions
* region_market_scores
* relevant company-region records, if route supports degraded output
State behavior
If region output is:
* fresh: return normally
* stale: return with freshness warning
* partial: return available sections and warnings
* failed/blocked: return error or degraded fallback if available
Must not do
* run full region build synchronously
* run company universe intake
* run broad presence mapping

⸻

GET /regions/{region_id}/companies
Purpose
Return companies present in a region.
Query params
Optional:
* eligible_only=true|false
* major_tech=true|false
* mag7=true|false
* currently_hiring=true|false
* entry_level=true|false
* sector=software|ai|cloud|data|hardware|cybersecurity
* limit
* offset
Response data
{
  "region_id": "greater_boston",
  "companies": [
    {
      "company_id": "comp_101",
      "company_name": "Example AI",
      "sector_primary": "ai",
      "eligibility_status": "eligible",
      "is_major_tech": true,
      "is_mag7": false,
      "presence_status": "present",
      "presence_basis": "office_plus_hiring",
      "currently_hiring_flag": true,
      "entry_level_access_score": 0.81
    }
  ]
}
Reads from
* companies
* company_region_presence
* company_region_hiring
* company_region_entry_level
Must not do
* mutate company truth
* run classification live

⸻

GET /regions/{region_id}/hiring
Purpose
Return hiring summary for a region.
Query params
Optional:
* role_family
* entry_level=true|false
* major_tech=true|false
* limit
* offset
Response data
{
  "region_id": "greater_boston",
  "hiring_summary": {
    "actively_hiring_company_count": 42,
    "active_posting_count_now": 214,
    "posting_count_30d": 480,
    "posting_count_90d": 1200
  },
  "companies": []
}
Reads from
* company_region_hiring
* company_region_entry_level
* companies
Must not do
* fetch live job postings synchronously
* perform external source ingestion

⸻

GET /regions/{region_id}/entry-level
Purpose
Return early-career opportunity summary for a region.
Query params
Optional:
* role_family
* major_tech=true|false
* limit
* offset
Response data
{
  "region_id": "greater_boston",
  "entry_level_summary": {
    "internship_count": 25,
    "coop_count": 18,
    "entry_level_full_time_count": 34,
    "formal_early_career_program_count": 12,
    "early_career_accessibility_score": 0.79
  },
  "companies": []
}
Reads from
* company_region_entry_level
* company_region_hiring
* companies
* region_market_scores
Must not do
* treat unknown role metadata as zero
* run job parsing live

⸻

5. Company APIs
GET /companies/{company_id}
Purpose
Return assembled company output object.
Response data
{
  "company": {
    "company_id": "comp_101",
    "company_name": "Example AI",
    "sector_primary": "ai",
    "eligibility_status": "eligible",
    "is_major_tech": true,
    "is_mag7": false,
    "prestige_score": 0.77,
    "regions_present": [],
    "regions_hiring": [],
    "entry_level_regions": []
  }
}
Reads from
Preferred:
* company_outputs
Fallback:
* companies
* company-region presence/hiring/entry-level records
Must not do
* classify company live
* run external company research

⸻

GET /companies/{company_id}/regions
Purpose
Return where a company is present, hiring, and entry-level accessible.
Query params
Optional:
* present_only=true|false
* currently_hiring=true|false
* entry_level=true|false
Response data
{
  "company_id": "comp_101",
  "regions": [
    {
      "region_id": "greater_boston",
      "display_name": "Greater Boston",
      "presence_status": "present",
      "presence_basis": "office_plus_hiring",
      "currently_hiring_flag": true,
      "active_posting_count_now": 12,
      "entry_level_access_score": 0.81
    }
  ]
}
Reads from
* companies
* regions
* company_region_presence
* company_region_hiring
* company_region_entry_level

⸻

GET /companies/{company_id}/hiring
Purpose
Return company hiring footprint across supported regions.
Query params
Optional:
* region_id
* entry_level=true|false
* role_family
Response data
{
  "company_id": "comp_101",
  "hiring_by_region": [
    {
      "region_id": "greater_boston",
      "currently_hiring_flag": true,
      "active_posting_count_now": 12,
      "posting_count_30d": 24,
      "posting_count_90d": 55,
      "entry_level": {
        "internship_count": 3,
        "coop_count": 2,
        "entry_level_full_time_count": 4
      }
    }
  ]
}
Must not do
* fetch live postings synchronously
* mutate hiring records

⸻

6. Comparison APIs
GET /compare
Purpose
Compare two supported regions.
Query params
Required:
* region_a
* region_b
Optional:
* role_family
* entry_level=true|false
* personalized=true|false
Example:
GET /compare?region_a=greater_boston&region_b=greater_sf
Response data
{
  "comparison": {
    "comparison_id": "greater_boston__greater_sf",
    "region_a": {
      "region_id": "greater_boston",
      "scores": {}
    },
    "region_b": {
      "region_id": "greater_sf",
      "scores": {}
    },
    "category_winners": {
      "structural_ecosystem": "greater_sf",
      "early_career_accessibility": "greater_boston",
      "objective_opportunity": "greater_boston"
    },
    "notes": []
  }
}
Reads from
Preferred:
* cached comparison_outputs
Fallback:
* region_outputs
Allowed live work
* lightweight comparison assembly from region outputs
* lightweight filtering
Must not do
* recompute region scores from scratch synchronously
* run hiring refresh synchronously
* run presence mapping synchronously

⸻

GET /compare/contextual
Purpose
Return secondary contextual challenge output for a comparison.
Query params
Required:
* comparison_id
Alternative:
* region_a
* region_b
Response data
{
  "contextual_challenge": {
    "comparison_id": "greater_boston__greater_sf",
    "challenge_status": "challenged",
    "changed_findings": [],
    "unchanged_findings": [],
    "explanation": ""
  }
}
Reads from
* contextual_challenge_outputs
* comparison_outputs
Allowed live work
* lightweight contextual challenge generation if base comparison exists
Must not do
* replace primary comparison score
* mutate region scores
* treat contextual challenge as canonical truth

⸻

7. Search / Filter APIs
GET /search/companies
Purpose
Search companies across supported regions and filters.
Query params
Optional:
* q
* region_id
* sector
* major_tech
* mag7
* currently_hiring
* entry_level
* limit
* offset
Response data
{
  "companies": [
    {
      "company_id": "comp_101",
      "company_name": "Example AI",
      "sector_primary": "ai",
      "is_major_tech": true,
      "regions": []
    }
  ]
}
Reads from
* companies
* company-region tables
Must not do
* semantic search unless explicitly implemented
* external web lookup

⸻

GET /search/regions
Purpose
Search or filter supported regions.
Query params
Optional:
* q
* region_type
* min_objective_score
* role_family
* entry_level=true|false
Response data
{
  "regions": [
    {
      "region_id": "greater_boston",
      "display_name": "Greater Boston",
      "objective_opportunity_score": 0.74,
      "early_career_accessibility_score": 0.79
    }
  ]
}
Reads from
* regions
* region_market_scores

⸻

8. Personalized Discovery APIs
POST /discover/personalized
Purpose
Return personalized region and company rankings from user preferences.
Request body
{
  "role_targets": ["product"],
  "industry_preferences": ["ai", "cloud"],
  "career_stage": "entry_level",
  "prestige_preference": "medium",
  "brand_preference": "medium",
  "region_ids": ["greater_boston", "greater_sf"],
  "limit": 25
}
Response data
{
  "personalized": {
    "ranked_regions": [
      {
        "region_id": "greater_boston",
        "personal_market_score": 0.78,
        "objective_opportunity_score": 0.74
      }
    ],
    "ranked_companies": [
      {
        "company_id": "comp_101",
        "region_id": "greater_boston",
        "personal_company_score": 0.84,
        "match_notes": []
      }
    ]
  }
}
Reads from
* region_market_scores
* companies
* company_region_hiring
* company_region_entry_level
* derived output objects if useful
Writes to
* session cache only, if implemented
Must not do
* mutate canonical truth
* create permanent user profile unless explicitly requested
* run foundational rebuilds

⸻

9. Minimal Admin/Internal APIs
These are not public product APIs.
They may be implemented only when needed for orchestration/testing/admin workflows.
POST /admin/jobs/run
Purpose
Manually enqueue a job.
Request body
{
  "job_type": "hiring_refresh",
  "scope": {
    "region_ids": ["greater_boston"]
  },
  "priority": "normal"
}
Response data
{
  "job_id": "job_123",
  "status": "queued"
}
Must protect
This endpoint should be internal/admin only.

⸻

POST /admin/refresh/region
Purpose
Trigger region refresh workflow.
Request body
{
  "region_id": "greater_boston",
  "refresh_scope": "hiring_and_entry_level"
}
Response data
{
  "queued_jobs": ["job_123", "job_124"]
}

⸻

POST /admin/refresh/company
Purpose
Trigger company refresh workflow.
Request body
{
  "company_id": "comp_101",
  "refresh_scope": "hiring"
}
Response data
{
  "queued_jobs": ["job_125"]
}

⸻

10. Error Codes
MVP APIs should use consistent error codes.
Recommended error codes:
* NOT_FOUND
* VALIDATION_ERROR
* OBJECT_STALE
* OBJECT_PARTIAL
* OBJECT_BLOCKED
* OBJECT_FAILED
* DEPENDENCY_MISSING
* UNSUPPORTED_FILTER
* INTERNAL_ERROR
Example:
{
  "status": "error",
  "data": null,
  "metadata": {
    "state": "blocked",
    "warnings": []
  },
  "error": {
    "code": "OBJECT_BLOCKED",
    "message": "Comparison cannot be built because one region output is unavailable."
  }
}

⸻

11. Freshness and State Exposure
Where useful, responses should expose:
* object state
* last updated time
* freshness expiry
* warnings
* source versions
Do not hide stale or partial data.
If a response uses stale data, return it honestly.
Example warning:
{
  "warning_code": "STALE_REGION_OUTPUT",
  "severity": "medium",
  "message": "Region output is older than the preferred freshness window."
}

⸻

12. API Non-Goals for MVP
Do not implement unless explicitly requested:
* frontend routes/pages
* authentication-heavy user account system
* employer accounts
* application submission
* resume upload
* saved job tracking
* messaging
* full admin dashboard
* semantic natural-language search
* raw job posting CRUD APIs
* public mutation APIs for canonical truth

⸻

13. MVP Endpoint List
Required MVP endpoints:
GET  /health
GET  /regions
GET  /regions/{region_id}
GET  /regions/{region_id}/companies
GET  /companies/{company_id}
GET  /companies/{company_id}/regions
GET  /compare
POST /discover/personalized
Recommended if slice reaches them:
GET  /regions/{region_id}/hiring
GET  /regions/{region_id}/entry-level
GET  /companies/{company_id}/hiring
GET  /compare/contextual
GET  /search/companies
GET  /search/regions
Internal/admin only:
POST /admin/jobs/run
POST /admin/refresh/region
POST /admin/refresh/company

⸻

14. Implementation Guidance
When implementing APIs:
1. keep route handlers thin
2. put business logic in services
3. read cached/derived outputs first when available
4. expose state/freshness metadata
5. do not run heavy rebuilds synchronously
6. validate filters explicitly
7. return partial data honestly
8. avoid inventing endpoints not listed here

⸻

15. API Acceptance Criteria
The MVP API surface is acceptable when it can:
1. return supported regions
2. return a region output
3. return companies in a region
4. return a company output
5. return company regions
6. compare two supported regions
7. run personalized discovery from request-scoped preferences
8. expose state/freshness metadata
9. avoid heavy truth-building in request handlers
10. return structured errors for missing/stale/blocked objects
