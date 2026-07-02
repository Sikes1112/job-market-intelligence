# Layer 17 Career Platform Integrations

Batch 17C implements safe manual/export/deep-link career platform workflows.
Career platforms are destinations and references, not dependencies or product
authorities.

## Domain Model

- `CareerPlatform`
- `CareerPlatformReference`
- `CareerPlatformExport`
- `CareerPlatformRiskPosture`
- `ExternalCareerLink`

Risk posture values:

- `safe_manual`
- `export_only`
- `deep_link_only`
- `official_api_only`
- `requires_review`
- `blocked_hostile_tos`
- `deferred`

## Implemented Workflows

- Export company/employer lists for manual LinkedIn search.
- Export employer lists for manual Handshake lookup.
- Store public company career page URLs as manual references.
- Show manual company career page/open-link posture.
- Show manual search/deep-link posture for LinkedIn and Handshake.
- Display platform registry posture and blocked capabilities.

## Explicitly Blocked

- LinkedIn scraping
- Handshake automation
- job-board crawling behind login
- automated application submission
- automated resume upload
- automated recruiter messaging
- employer CRM behavior
- applicant tracking
- candidate/application status pipelines

Career platform exports persist `manual_only: true` and false values for
automation, ATS state, application status creation, and recruiter outreach.

## API Routes

- `GET /api/integrations/career-platforms`
- `GET /api/integrations/career-platforms/companies/{company_id}/links`
- `POST /api/integrations/career-platform-references`
- `GET /api/integrations/career-platform-references`
- `POST /api/integrations/career-platform-exports`

All routes require authenticated app users. Institution-scoped references and
exports require active institution permissions.

## Frontend

Company integration controls expose LinkedIn and Handshake manual export
actions. Account settings expose the platform registry and sample manual export
actions. The UI labels deferred/blocked automation states instead of showing
broken live-sync buttons.
