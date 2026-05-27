# Layer 16 Closeout

## Scope

Layer 16 turns the product into an education-privacy-aware institutional
surface for schools, career centers, bootcamps, workforce organizations, and
economic-development partners.

Implemented coverage:

- Batch 16A: organization accounts, memberships, roles, permission helpers,
  institutional API shell, audit-log foundation, and cross-organization tests.
- Batch 16B/16C: aggregate-first cohort dashboard, minimum group suppression,
  low-sample metadata, institutional dashboard API, and frontend dashboard.
- Batch 16D: guidance-oriented advisor tools for regions, industries,
  companies, career stages, and application timing.
- Batch 16E: aggregate institutional reports and auditable export/deletion
  request records.
- Batch 16F: final privacy, permission, migration, threshold, documentation,
  and validation hardening.

## Final Capabilities

- Organizations are first-class account boundaries.
- Memberships carry persisted `ORG_ADMIN`, `ADVISOR`, `STUDENT`, and
  `REPORT_VIEWER` roles.
- Cohort dashboards expose aggregate career-interest and market-alignment
  summaries only.
- Advisor tools provide market guidance and comparison support without
  inspecting individual student behavior.
- Institutional reports are persisted aggregate-first payloads for career
  services, program directors, workforce planners, and economic-development
  partners.
- Data export/deletion workflows create auditable request records only.
- Institutional audit logs record organization, member, dashboard, advisor,
  report, and data-request actions.

## Privacy And Permission Guarantees

- Backend membership checks are the security boundary; frontend role state is
  display context only.
- Organization-scoped endpoints require active membership in the requested
  organization.
- Membership in one organization does not authorize access to another
  organization.
- Students do not access institution-wide dashboards, advisor tools, reports,
  member management, or other students' data-request records by default.
- Report viewers cannot manage members, use advisor tools, or create
  export/deletion requests.
- Advisors cannot create export/deletion request records by default.
- Organization admins can create/list organization-level request records only.
- Student data requests are scoped to the requesting student.
- The public dashboard/report minimum group lower bound is `5`; overrides below
  `5` are rejected.
- Low-sample categories are suppressed before serialization. Hidden labels and
  exact hidden student counts are not exposed.
- Institutional payloads do not expose raw per-student searches, saved rows,
  recommendation snapshots, preferences, alerts, or personal activity.
- Audit metadata is organization-scoped and avoids private student-level
  payload data.

## Privacy Posture

The Layer 16 foundation is education-privacy-aware and FERPA-conscious in
design, but this implementation does not claim legal FERPA compliance. It
minimizes unnecessary student-level exposure through role checks, organization
scoping, aggregate-first dashboard/report design, and deferred student-specific
consent workflows.

## Deferred

- PDF/CSV/PowerPoint exports
- Email delivery and scheduled reports
- Destructive deletion execution
- Full export package generation
- Explicit student consent workflow
- Student-specific advising mode
- Private student activity inspection
- Enterprise billing
- SSO
- Invite/onboarding flows
- Full FERPA compliance system

## Validation

Final lock validation passed on the current worktree with:

- `.venv/bin/python -m pytest tests/test_institutions_foundation.py tests/test_institutional_dashboard.py tests/test_institutional_advisor_tools.py tests/test_institutional_reports_data_requests.py tests/test_schema_completeness.py tests/test_migrations.py tests/test_auth_user_foundation.py tests/test_api_user_routes.py tests/test_public_demo_environment.py tests/test_api_protection.py tests/test_smoke_imports.py`
  - `293 passed`
- `.venv/bin/ruff check backend tests alembic`
  - passed
- `npm --prefix frontend run test`
  - `10` test files and `41` tests passed
- `npm --prefix frontend run lint`
  - passed
- `npm --prefix frontend run build`
  - passed with the existing Vite chunk-size warning
- `git diff --check`
  - passed

## Lock Recommendation

Layer 16 is ready to lock.
