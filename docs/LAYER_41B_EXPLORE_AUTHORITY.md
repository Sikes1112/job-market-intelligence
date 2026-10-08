# Layer 41B Explore Context and Fit authority

## Jurisdictions

The redesigned product has one authority per question:

- **Explore Fit** is the individual geographic-exploration authority: “Where should I look?”
- **Layer 34 Market Intelligence** is the governed market-evidence authority consumed by Explore Fit.
- **Layer 38 Current Opportunities** is the current-job matching authority. Its coverage is displayed beside Fit and never enters the Fit score or order.
- **Layer 36** becomes authoritative only after a durable Decision exists.
- **Layer 37** owns deeper and longitudinal analysis of durable Decisions.
- **Career Agent** orchestrates and explains authoritative outputs. New geographic integrations use `CareerAgentAuthorityAdapter`; they do not call its legacy city-scoring path.

Personalized Discovery retains company/preference primitives and its compatibility routes. Public Layer 14 Recommendations, the Layer 30.1 Dashboard recommendation assembly, legacy Career Agent scoring, and Opportunity Routes remain compatibility/internal capabilities. None is imported by `backend.explore`.

## Explore Context

Explore Context is request-scoped and is not another profile store. It contains the Career Identity ID/version and consent state, normalized supported defaults, explicit session overrides, effective context, support metadata, and a deterministic `explore_context_v2` fingerprint. Version 2 sorts and deduplicates every set-like semantic field before hashing; the version changed because reproducing a v1 hash must retain v1's order-sensitive behavior.

Precedence is field-by-field:

1. explicit session override;
2. consented Career Identity default;
3. neutral empty product default.

The fingerprint is SHA-256 over versioned semantic context, identity version, consent, and personalization outcome. It excludes viewport, pan, hover, and presentation state. Overrides are returned visibly and never mutate Career Identity.

Career Identity `target` and `acceptable` Regions are soft preferences. Only explicit session scope and explicit exclusion facts enter the hard include/exclude sets. Canonical include/exclude conflicts return `needs_input` instead of applying precedence within the effective set.

Career Identity currently supplies supported role/goal signals, role families, employment/opportunity type, seniority/career stage, preferred industries, work arrangement, canonical geographic constraints, and categorical timing. Compensation, unresolved geography, exclusions without governed evidence, conflicting career stages, and other unsupported facts are returned as categorical unapplied items; raw résumé text and free-form private facts are never copied into Explore output or analytics.

Outcomes are `personalized`, `needs_input`, `general_market_intelligence`, and `unsupported`. Career Identity completeness is not duplicated: Explore uses the available supported fields and can provide general intelligence when personalized Fit is unavailable. No-consent identities are not read for personalization. Explicit request-scoped inputs can still produce Fit because the user supplied them for that evaluation.

## Initial role/goal mapping

Mapping is deterministic and versioned with the Explore algorithm. Initial governed targets are:

- software engineer/software engineering/SWE/backend or frontend engineer → `software_engineering`;
- product manager/product management/technical product manager → `product_management`;
- AI/ML, machine-learning, ML-engineer, AI-engineer, or artificial-intelligence roles → `ai_ml`;
- cybersecurity/cyber security/security engineer/information security → `cybersecurity`;
- data science/data scientist → `data_science`.

Canonical goal keys are accepted directly. Multiple matches require an explicit goal. An unmapped role produces unsupported personalized Fit; general governed market intelligence can still be returned. `data_science` is a recognized goal but Layer 34 currently abstains because direct evidence is not collected.

## Explore Fit composition

Explore Fit calls Layer 34 once for the effective governed goal. It preserves Layer 34 score, confidence, freshness, evidence sufficiency, drivers, tradeoffs, contradictions, robustness grounding, missing evidence, and abstention. It does not average legacy scores or apply arbitrary preference bonuses.

The individual Career Agent routes are `/me/career-agent/answers` and its compatibility alias `/career-agent/answers`. Geographic questions consume Explore Fit, current-job questions consume Layer 38, and existing durable decisions consume Layer 36 with Layer 37 analysis when available. The old Layer 26 scorer is available only at the undocumented, deprecated `/internal/legacy/career-agent/answers` compatibility path.

Geographic include/exclude scope and canonical Region support status are the currently enforceable hard constraints. Work arrangement, industry, timing, and opportunity-type preferences remain visible context but do not alter a market score until governed market evidence supports those dimensions. Role preference affects Fit by selecting the governed goal model, not by adding a bonus.

Eligible results use the Layer 34 score and deterministic canonical-region tie breaking. Exact ties share rank. Differences at or below Layer 34’s `0.01` near-tie threshold are labeled. Insufficient/not-supported or blocking-contradiction results have no Fit score or rank.

`explore_fit_bands_v1` is provisional presentation calibration over sufficient Layer 34 scores: at least `0.70` is `strong_fit`, at least `0.50` is `good_fit`, and lower sufficient scores are `possible_fit`. Limited evidence is always `limited_evidence`, irrespective of score. These constants may be tuned without changing authority boundaries; unknown evidence never becomes zero.

## Coverage separation

`market_coverage` comes from Layer 34 grounding. `opportunity_coverage` comes from Layer 38 contracts and aggregated active/fresh/ranking-eligible job counts. Opportunity aggregation happens only after Fit scoring and ranking. The opportunity contract includes `affects_explore_fit: false`; tests vary ingestion from zero to 20 records without changing Fit score or rank.

## API and supported universe

Authenticated routes are:

- `GET /me/explore/context` — current consent-aware defaults;
- `POST /me/explore/markets` — batch evaluation with explicit ephemeral overrides;
- `POST /me/explore/markets/{market_ref}` — selected-market summary from the same facade.

The output includes canonical Region ID, public slug, display name, state membership, nullable centroid/bounds, and support status. It is map-ready but contains no map UI state.

The current ranking universe is the eight-market curated registry (or an explicit geographic subset): New York, Seattle, San Francisco Bay Area, Boston, Washington DC, Austin, Atlanta, and Chicago. It is explicitly not nationally representative.

Results carry `explore_fit_v1`, Layer 34 authority version, a content-derived market-evidence bundle hash, `explore_fit_bands_v1`, Career Identity version, context fingerprint, and evaluation time. Ephemeral results are not persisted.

## Measurement and privacy

Layer 40 records only `explore_context_evaluated` plus one material outcome (`explore_fit_generated`, `explore_fit_abstained`, or `explore_context_unsupported`). Payloads contain categorical state, governed goal, counts, versions, and the fingerprint—not raw identity facts, résumé/profile text, or recommendation narratives.
