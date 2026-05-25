# Layer 11 Closeout: Retention and Product Expansion Layer

Date: 2026-05-25

## Purpose

Layer 11 builds recurring product value after the application is credible,
useful, and safe. It adds user retention surfaces, in-app change awareness,
repeatable region expansion workflow contracts, read-only product
visualizations, and deterministic structured guidance while preserving the
existing market-truth, scoring, provenance, admin, refresh, and ingestion
boundaries.

## Completion Decision

COMPLETE_WITH_NARROW_AUDIT_FIXES_ACCEPTED

Layer 11 can be locked. The final accepted narrow audit fix tightened
explanation evidence-packet validation so copied market-payload key names are
rejected before deterministic guidance rendering.

## Final Validation Status

- `python -m pytest`: 1618 passed
- `python -m ruff check backend tests alembic`: passed
- `cd frontend && npm run test`: 16 passed
- `cd frontend && npm run build`: passed
- `cd frontend && npm run lint`: passed

## Areas Changed

- Protected user/account APIs under `/me`
- User preference and saved market artifact services
- Personalization scoring controls and scoring-preview overlays
- Alert event and user alert services, repositories, and API routes
- Region expansion workflow contracts, candidates, and gating rules
- Frontend account dashboard, watchlists, alerts, scoring controls, read-only
  visualizations, and structured guidance panels
- Deterministic explanation evidence-packet contracts and rendering service
- Alembic migrations for Batch 11A and Batch 11B
- Backend, frontend, migration, schema, public-demo, and boundary tests
- API, data model, auth/user, public-demo, frontend, and README documentation

## Batch Summaries

### Batch 11A: Retention Foundation

- Added saved watchlists for companies, regions, role families, and comparison
  sets.
- Added user scoring controls with adjustable weights.
- Added personalized scoring preview/overlay behavior.
- Labeled canonical/default scores separately from personalized scores.
- Enforced server-side reference-only saved artifact snapshots.
- Added fallback to default weights for malformed persisted
  `scoring_weights`; request-time malformed weights remain rejected.

### Batch 11B: Change/Expansion Engine

- Added `AlertEvent` for system-level structured change metadata.
- Added `UserAlert` for user-specific relevance, read, and dismissed state.
- Added protected in-app alert routes under `/me/alerts`.
- Added alert read/dismiss behavior and watchlist/preference relevance
  matching.
- Added a region expansion workflow contract and target candidate set for NYC,
  Seattle, Austin, DC/NoVA, Boston, SF, Atlanta, Chicago, and LA.
- Added publish and refresh-enabled gates without creating another ingestion
  system.

### Batch 11C: Product Surface and Explanation

- Added read-only score breakdown visualization.
- Added read-only region comparison visualization.
- Added read-only alert summary visualization.
- Added disabled/unsupported states for trends, maps, heatmaps,
  company-region network graph, and region expansion visualization where safe
  data or API support is missing.
- Added deterministic structured guidance explanation endpoints under
  `/me/explanations/*`.
- Added evidence-packet validation against copied market payloads.
- Did not add external AI provider integration.
- Did not persist explanation output.

## Boundary Preservation Summary

- No new market-truth source was added.
- No canonical scoring overwrite path was added.
- No copied canonical market payloads are allowed in saved artifacts, alert
  records, or explanation evidence packets.
- No second ingestion system was added.
- No admin, provenance, or refresh bypass was added.
- No external AI provider was added.
- No AI-generated market facts were added.
- No email or push notification delivery was added.
- No unsupported map, trend, heatmap, network, or region-expansion
  visualization precision is shown as active.

## Deferred Items

- External AI provider integration
- Real trend views backed by durable historical snapshots
- Maps backed by safe geographic metadata
- Heatmaps backed by supported density/cell data
- Company-region network graph backed by supported relationship/layout data
- Region expansion status visualization backed by a safe frontend/API contract
- Alert automation from durable historical refresh/output history
- Email and push notification delivery

## Recommendation

Layer 11 can be locked. Future work should begin from the deferred items or the
next roadmap layer, not by reopening Layer 11 core boundaries.
