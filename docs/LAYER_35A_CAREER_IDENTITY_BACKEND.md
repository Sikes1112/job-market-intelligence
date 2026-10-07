# Layer 35A Career Identity Backend

Layer 35A adds a canonical user-owned Career Identity aggregate. It is app-user
data scoped by `users.user_id`; it does not replace Auth0 identity, internal
account identity, market truth, recommendations, or frontend profile state.

## Source Of Truth

- `career_identities` is the aggregate root for one internal user.
- `career_identity_facts` stores normalized typed facts for education,
  experience, skills, projects, credentials, goals, preferences, geography,
  compensation, timing, and work arrangement.
- `career_identity_imports` stores safe resume/profile import metadata. Raw
  submitted text or document content is not retained or exposed through ordinary
  identity APIs.

Existing `user_preference_profiles` remains a personalization input table for
legacy recommendation overlays. Layer 35B adds the application-level authority
rule: authenticated Career Identity is canonical for Layer-35-covered
user-facing career facts and preferences, and recommendations consume it through
a read adapter rather than by taking ownership of career facts.

## Provenance And State

Each fact has one acquisition state:

- `explicit`: directly entered by the user.
- `imported`: obtained from a submitted resume/profile/import.
- `inferred`: derived by system logic.
- `confirmed`: explicitly validated by the user.

Precedence is deterministic:

```text
confirmed > explicit > imported > inferred
```

Weaker facts cannot silently overwrite stronger facts for the same normalized
fact key. A protected duplicate/import is recorded in provenance history rather
than replacing the stronger payload.

## Versioning

`career_identities.current_version` starts at `1` and increments on meaningful
fact, consent, privacy, confirmation, deletion, or ingestion mutations. Reads
and no-op duplicate updates do not advance the version. Mutation requests may
send `expected_version`; mismatches return a conflict.

## Completeness And Sufficiency

Completeness is deterministic and section-weighted:

- background: education, experience, projects, credentials
- skills
- goals
- role and industry preferences
- geography and work arrangement
- compensation and timing

Sufficiency requires enough background, skill, goal, role/preference, and
location/work signals for downstream career intelligence. Imported/inferred
facts count as weak signals until the user confirms or explicitly corrects
them. The evaluator returns machine-readable missing and weak reason codes
bound to the identity version.

## API Boundary

Protected `/me/career-identity` routes are scoped to the authenticated internal
user and never accept a client-supplied owner id. They expose current identity,
privacy/consent, fact upsert/update/delete/confirm, evaluation, and safe
resume/profile ingestion.

Layer 35B UI, recommendation personalization integration, and workflow coverage
are documented in `docs/LAYER_35_CAREER_IDENTITY_CLOSEOUT.md`.
