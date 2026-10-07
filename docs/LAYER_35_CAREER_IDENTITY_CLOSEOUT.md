# Layer 35 Career Identity Intelligence Closeout

Layer 35 is implemented as a user-owned Career Identity source of truth plus a
frontend workspace and recommendation-personalization adapter.

## Source Of Truth

Career Identity remains owned by `career_identities` and `career_identity_facts`
under the canonical internal `users.user_id`. The frontend reads and mutates
Career Identity through `/me/career-identity` APIs only; it does not maintain a
separate career profile or onboarding JSON store.

`user_preference_profiles` remains for legacy saved overlay compatibility. For
Layer-35-covered career facts and career preferences, authenticated user-facing
Career Identity is authoritative. Recommendation personalization now uses a
read adapter from Career Identity into the existing in-memory
`UserPreferences` shape rather than dual-writing the legacy preference table.

## Frontend Surfaces

The product route `/markets/career-identity` exposes a single Career Identity
workspace with:

- guided onboarding steps for background, skills/projects, goals, roles and
  industries, location/work style, compensation/timing, and review;
- manual entry forms for every Layer-35 fact type;
- supported resume/profile import for `resume_text`, `profile_text`, and
  `structured_profile` JSON;
- a profile editor listing current facts grouped by domain category;
- review actions for imported/inferred facts: confirm, edit/correct, and
  remove;
- backend-driven completeness/sufficiency status and missing-section guidance;
- consent/privacy controls backed by the Career Identity privacy API;
- a Career Identity personalized recommendation preview.

The existing Personalized Discovery page also uses Career Identity for
authenticated active accounts by calling `/me/discover/personalized`. Anonymous
and unauthenticated discovery continues to use the request-scoped public
`/discover/personalized` endpoint.

## Provenance And Review

Fact states are displayed with user-facing labels:

- `explicit`: Added by you
- `imported`: Imported
- `inferred`: Suggested
- `confirmed`: Confirmed

Imported and inferred facts appear in a focused review queue. Confirming a fact
uses `/me/career-identity/facts/{fact_id}/confirm`; correcting uses the update
API and writes explicit user truth; rejecting/removing uses the delete API. Raw
imported resume/profile text is not displayed.

## Completeness And Sufficiency

The client consumes `/me/career-identity/evaluation` and the identity's
`completeness` snapshot. It does not re-score identity readiness. Frontend
guidance maps backend reason codes to stable user-facing next actions, and the
display shows the identity version associated with the evaluation.

## Privacy

The workspace exposes backend-supported controls for:

- resume/profile ingestion consent;
- inference consent;
- downstream recommendation personalization consent;
- safe import metadata retention.

Saves include the current identity version. Failed saves show an error and do
not optimistically claim persistence. Ingestion uses the current ingestion
consent state and does not retain raw imported text.

## Recommendation Personalization Mapping

Authenticated `/me/discover/personalized` overlays canonical Career Identity
onto the existing `UserPreferences` payload when
`downstream_personalization_consent_granted` is true.

Mapped signals:

- preferred role preferences map to `role_targets`;
- excluded role preferences are removed from effective role targets and
  surfaced in metadata;
- preferred industries map to `industry_preferences`;
- excluded industries are removed from effective industry preferences and
  surfaced in metadata;
- geographic target/acceptable constraints are matched to known region ids when
  possible;
- geographic exclusions are removed from effective region ids when possible;
- skills and experience are exposed as metadata counts for auditability, while
  existing scoring formulas continue to use their current role/industry/region
  semantics.

No new ranking engine was introduced. The adapter feeds the existing
`PersonalizationService`; recommendation output and explanations remain
truthful to the role and industry components actually used by the scorer.

Fallback behavior:

- no Career Identity: use request-scoped preferences unchanged;
- Career Identity without downstream personalization consent: use request
  preferences unchanged and return metadata explaining consent was not granted;
- partial Career Identity: overlay available Career Identity preferences and
  retain request fallbacks for missing dimensions;
- legacy preference rows: preserved for existing account/settings features, but
  not treated as the canonical Layer-35 source when Career Identity is used.

## Error And Conflict Behavior

The frontend handles loading, empty, validation, mutation, import, privacy,
delete, confirm, recommendation refresh, and generic failure states. Mutation
requests send `expected_version`; `409 VERSION_CONFLICT` refetches the current
identity and asks the user to review the retained draft before retrying.

Validation responses use sanitized backend messages. The UI does not render raw
tracebacks or raw submitted resume/profile text.

## Supported Import Formats

Supported:

- pasted resume text;
- pasted profile text;
- structured profile JSON matching the backend ingestion schema.

Not supported in Layer 35:

- binary PDF parsing;
- DOCX parsing;
- new external AI extraction providers.

## Verification Coverage

Backend tests cover Career Identity lifecycle, provenance/precedence, ingestion,
privacy, completeness, APIs, and the authenticated Career Identity
personalization adapter.

Frontend tests cover guided manual entry, import/review/confirm/edit/remove,
privacy save, recommendation preview, validation redaction, version-conflict
recovery, empty/unauthenticated states, and reload persistence through the
component's API-backed state.

The repository does not currently include a separate browser E2E framework;
Layer 35 user workflows are covered through FastAPI integration tests and
Vitest/Testing Library component workflow tests.

## Remaining Non-Blocking Limits

- `expected_version` remains a service-level optimistic check rather than a
  fully atomic compare-and-update.
- Database-level composite user/root consistency remains enforced by service
  ownership rather than a composite foreign-key constraint.
- Evaluation read paths may flush completeness snapshots without advancing the
  identity version.
- Legacy saved preference settings remain available for compatibility.
