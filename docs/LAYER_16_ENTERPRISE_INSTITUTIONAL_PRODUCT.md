# Layer 16 Enterprise / Institutional Product Layer

## Batch Status

Batch 16A adds the institutional foundation and permission spine only. It does
not add advisor comparison tools, institutional reports, export/delete
workflows, enterprise billing, SSO, or student-consent workflows.

Batch 16B/16C adds privacy-aware cohort aggregation, the institution dashboard
API, and a frontend institutional dashboard view. It does not add
student-specific advising mode, institutional reports, exports, SSO, billing,
or full FERPA compliance workflows.

Batch 16D adds guidance-oriented advisor tools for comparing regions,
industries, companies, career stages, and application timing. It does not add
institutional reports, export/delete workflows, SSO, enterprise billing,
invite/onboarding flows, full student-consent workflows, or private individual
student activity inspection.

Batch 16E adds aggregate-first institutional reports and auditable institutional
data export/deletion request records. It does not add PDF/CSV/PowerPoint
exports, email delivery, scheduled reports, destructive deletion execution,
full export package generation, SSO, enterprise billing, or full consent
workflows.

## Institutional Domain

Organizations are first-class institutional account boundaries for schools,
career centers, bootcamps, workforce organizations, economic-development
partners, and internal demos.

Tables:

- `organizations`
- `organization_memberships`
- `institutional_audit_logs`
- `institutional_reports`
- `institutional_data_requests`

Supported organization types:

- `school`
- `career_center`
- `bootcamp`
- `workforce_org`
- `economic_development_partner`
- `internal_demo`

Supported membership roles:

- `ORG_ADMIN`
- `ADVISOR`
- `STUDENT`
- `REPORT_VIEWER`

Supported organization and membership statuses are `active` and `inactive`.
Invite/onboarding workflows are intentionally not implemented in Batch 16A.

## Permission Spine

Institutional authorization is enforced by backend helpers in
`backend/institutions/permissions.py`. Permission checks consider the current
internal user id, requested organization, persisted organization membership,
membership role, membership status, and requested action.

Current stance:

- `ORG_ADMIN` can administer organization-level member surfaces and view audit
  surfaces, and can view aggregate cohort dashboards for its own organization.
- `ADVISOR` can view aggregate institutional guidance/dashboard surfaces, but
  cannot manage members. `ADVISOR` can use advisor guidance tools and
  generate/view aggregate institutional reports.
- `REPORT_VIEWER` can view/generate aggregate dashboards/reports, but cannot
  manage members, use advisor guidance tools, or create data request records.
- `STUDENT` is an organization member but does not access institution-wide
  dashboards, reports, or member-management surfaces by default. `STUDENT`
  may create/list only their own student data request records.
- `ORG_ADMIN` can create/list organization-level data request records.
- Inactive memberships never authorize institutional access.
- Student-private data access returns false by default. Scoped student-specific
  advising and explicit consent are deferred to a later Layer 16 batch.

The API never trusts frontend role state for authorization. Client payloads may
request a target member role for an admin action, but the caller's authority is
always loaded from persisted backend membership state.

## API Shell

Implemented routes:

- `GET /api/institutions/organizations/current`
- `GET /api/institutions/organizations/{organization_id}`
- `GET /api/institutions/organizations/{organization_id}/dashboard`
- `GET /api/institutions/organizations/{organization_id}/members`
- `POST /api/institutions/organizations/{organization_id}/members`
- `PATCH /api/institutions/organizations/{organization_id}/members/{membership_id}`
- `POST /api/institutions/organizations/{organization_id}/advisor/compare-regions`
- `POST /api/institutions/organizations/{organization_id}/advisor/compare-industries`
- `POST /api/institutions/organizations/{organization_id}/advisor/compare-companies`
- `POST /api/institutions/organizations/{organization_id}/advisor/compare-career-stages`
- `POST /api/institutions/organizations/{organization_id}/advisor/application-timing`
- `POST /api/institutions/organizations/{organization_id}/reports`
- `GET /api/institutions/organizations/{organization_id}/reports`
- `GET /api/institutions/organizations/{organization_id}/reports/{report_id}`
- `POST /api/institutions/organizations/{organization_id}/data-requests`
- `GET /api/institutions/organizations/{organization_id}/data-requests`

The current-organizations route returns the caller's own active organization
memberships. Organization detail and member-management routes require backend
permission checks. Member responses expose membership ids, organization ids,
user ids, roles, statuses, and timestamps only; they do not expose profile
email, recommendations, saved companies, personal activity, or student-level
private data.

## Cohort Dashboard

Layer 16 cohort dashboards are aggregate-first. They are designed to help
institutions understand career interest and market alignment patterns without
exposing unnecessary student-level activity. Low-sample categories are
suppressed according to the configured minimum group threshold.

The dashboard payload includes:

- organization id/name and generation time
- `minimum_group_size`, default `5`, with API overrides bounded to `5` through `50`
- `cohort_size` and safe visible cohort summary counts
- popular target markets
- role interest distribution
- saved company trends
- market demand trends for visible target markets
- coverage gaps and data-quality warnings
- suppression metadata
- privacy notes and data-freshness metadata

Aggregation uses active `STUDENT` organization memberships plus existing
user-owned preference profiles and saved market artifacts. It does not create
new search/activity tracking and does not expose student ids, raw saved rows,
raw recommendation snapshots, individual searches, or personal activity.

Suppression behavior:

- A category is visible only when at least `minimum_group_size` distinct
  students contribute to it.
- Low-sample labels and exact low-sample counts are withheld.
- Suppressed categories may be represented as `Other / insufficient sample
  size` and section-level suppression metadata.
- Market demand and coverage-gap sections are derived only from target markets
  that already passed the aggregate threshold.

The frontend dashboard route is `/markets/institution`. It consumes the
institutional current-organizations endpoint and the dashboard endpoint with
Bearer-token auth; frontend role state is not used for security decisions.

## Advisor Tools

Layer 16 advisor tools are guidance-oriented. They help institutional advisors
compare regions, industries, companies, career stages, and application timing
using existing market intelligence, coverage, hiring, company search, and
explanation-style payload patterns. They do not provide unrestricted access to
individual student activity.

Advisor tool payloads include compared items, demand signals, explanation
summaries, tradeoffs, coverage warnings, freshness metadata, limitations, and
privacy notes. They do not include student ids, raw per-student saved/search
rows, recommendation snapshots, personal activity, or hidden student history.

Advisor endpoints require an active `ORG_ADMIN` or `ADVISOR` membership in the
requested organization. `REPORT_VIEWER` remains dashboard/report-oriented and
cannot use advisor tools in Batch 16D. `STUDENT` and inactive memberships are
denied. Cross-organization requests are denied by backend permission helpers.

The frontend advisor workspace is `/markets/institution/advisor`. It uses the
same organization context as the institutional dashboard and submits typed
advisor comparison requests to backend-protected endpoints. Frontend role state
is display context only and is not a security boundary.

Student-specific advising remains deferred. No endpoint in Batch 16D allows an
advisor to inspect an individual student's searches, saved companies,
recommendations, alerts, preferences, or activity history.

## Institutional Reports

Layer 16 institutional reports are aggregate-first and privacy-aware. They are
designed to help career services, program directors, workforce planners, and
economic development partners understand cohort-level career and market
patterns without exposing unnecessary student-level activity.

Supported report types:

- `career_services`
- `program_director`
- `workforce_planner`
- `economic_development_partner`

Reports are generated from the privacy-aware dashboard aggregation, market
demand trends, coverage warnings, and limitations. They enforce the same
minimum group threshold and low-sample suppression behavior as cohort
dashboards. Report payloads include structured sections, findings, metrics,
warnings, suppressions, limitations, recommended actions, data freshness, and
deferred export options.

Report generation uses the same conservative minimum group lower bound as the
dashboard API. Requests below `5` are rejected instead of reducing the privacy
threshold.

Reports are persisted in `institutional_reports` for later viewing. The stored
payload remains aggregate-first and does not include student ids, raw
per-student saved/search rows, recommendation snapshots, personal activity, or
individual histories. PDF, CSV, PowerPoint, email delivery, and scheduled report
workflows are deferred.

## Data Request Records

Data export/deletion workflows in this layer create auditable institutional
request records. They do not automatically execute destructive deletion or
generate full export packages in this batch.

Supported request types:

- `organization_export`
- `organization_deletion`
- `student_export`
- `student_deletion`

Supported statuses:

- `pending`
- `approved`
- `rejected`
- `completed`
- `canceled`

`ORG_ADMIN` can create/list organization-level request records for its own
organization. `STUDENT` can create/list their own student export/deletion
request records. Advisors and report viewers cannot create student export or
deletion requests by default. No user can create a student-level request for
another student in Batch 16E.

## Audit Foundation

`institutional_audit_logs` is an append-only model foundation for institutional
access and member-management events. Layer 16 records audit events for:

- `organization_viewed`
- `organization_members_viewed`
- `organization_member_added`
- `organization_member_updated`
- `institution_dashboard_viewed`
- `advisor_compare_regions_used`
- `advisor_compare_industries_used`
- `advisor_compare_companies_used`
- `advisor_compare_career_stages_used`
- `advisor_application_timing_used`
- `institutional_report_generated`
- `institutional_report_viewed`
- `institutional_reports_listed`
- `institutional_data_request_created`
- `institutional_data_requests_listed`

The audit model stores organization scope, actor user id, actor role, action,
target type/id, purpose, metadata, and creation timestamp. It does not expose an
audit dashboard.

## Privacy Posture

The Layer 16 foundation is education-privacy-aware and FERPA-conscious in
design, but this implementation does not claim legal FERPA compliance. It
minimizes unnecessary student-level exposure through role checks, organization
scoping, and aggregate-only dashboard design.

Institutional membership grants access to institutional surfaces only. It does
not grant unrestricted access to student searches, saved companies,
recommendations, personal activity, or account data.

## Cross-Organization Isolation

Every organization-scoped route checks the caller's active membership in the
requested organization. Membership in Organization A does not authorize access
to Organization B. Member-management routes require an active `ORG_ADMIN`
membership in the same organization named in the route.

## Deferred

- Student-specific advising mode
- PDF/CSV exports
- PowerPoint exports
- Email delivery and scheduled reports
- Destructive deletion execution
- Full export package generation
- Explicit student consent workflow
- Enterprise billing
- SSO
- Invite/onboarding flows
- Private student activity inspection
