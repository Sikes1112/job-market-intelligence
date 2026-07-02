# Layer 19 - Category Ownership Layer

Layer 19 makes the product publicly legible as an Opportunity Geography
Intelligence and Career Market Intelligence platform. It owns category
language, public explanation posture, and methodology framing.

It does not own market data authority, recommendation authority, pricing,
institutional permissions, refresh behavior, or personalization behavior.

## Purpose

- Name the category clearly enough that public users understand the product is
  market intelligence, not merely a job board.
- Define shared vocabulary for opportunity geography, career market
  intelligence, company-region presence, early-career access, market fit,
  regional opportunity density, and career-market signal.
- Establish public methodology foundations for future reports and benchmarks.
- Keep public explanations honest about source coverage, freshness, confidence,
  limitations, demo data, and unknowns.

## Boundaries

Layer 19 may:

- define public category vocabulary
- document methodology posture
- add public glossary and methodology explanation pages
- add public report registries, payload contracts, and explanation pages that
  expose methodology, limitations, freshness, confidence, warnings, and
  public-safe provenance
- add public benchmark/index registries, payload contracts, and explanation
  pages that expose score-display caveats, subscores, methodology, limitations,
  freshness, confidence, warnings, and public-safe provenance
- add public SEO/content pages that use Layer 19 category language and link to
  public reports and benchmarks without creating unsupported claims
- add public citation, share-summary, source-authority, related-asset, and
  institutional CTA presentation surfaces
- describe how reports and benchmarks should disclose evidence, coverage,
  freshness, confidence, and limitations
- add tests proving category language artifacts and public pages exist

Layer 19 must not:

- create report rankings
- create benchmark scoring
- change recommendation ranking or recommendation assembly
- change market coverage, ingestion, refresh, or source authority
- turn public report templates into hidden scoring, ranking, benchmark, or index
  authority
- turn public benchmark/index templates into production scoring authority
- turn public SEO/content pages into generic blog spam, unsupported rankings, or
  hidden scoring authority
- turn citation, share, or source-authority labels into production scoring,
  coverage, recommendation, or institution-permission authority
- change billing, entitlements, plans, or checkout behavior
- change institutional permissions or institutional reporting authority
- change personalization controls, saved artifacts, alerts, or account data
- mutate canonical company, region, scoring, hiring, entry-level, output, or
  platform-intelligence records

## Batch 19A - Category Language + Methodology Foundation

Batch 19A implements the language and public explanation foundation only.

Included:

- `docs/CATEGORY_LANGUAGE.md`
- `docs/PUBLIC_REPORT_METHODOLOGY.md`
- `docs/BENCHMARK_METHODOLOGY.md`
- public glossary and methodology pages when the frontend has existing public
  routing support
- focused tests for documentation artifacts and public page rendering

Excluded:

- published rankings
- benchmark score formulas
- new report generation behavior
- new API authority
- new database tables
- new background jobs
- changes to recommendations, coverage, refresh, billing, institution, or
  personalization layers

## Batch 19B - Public Report Infrastructure

Batch 19B implements the public report system that can publish recurring
career-market intelligence report artifacts.

Included:

- public report payload contracts and validation
- a static public report registry for the initial report family
- read-only public API routes for listing and retrieving public reports
- frontend report listing and detail pages
- report cards, methodology blocks, limitations, freshness/confidence badges,
  warnings, source/provenance summaries, and related links
- tests proving report templates exist, required disclosures are present,
  internal-only fields are rejected, public-safe freshness/confidence/provenance
  are preserved, public routes render, and unknown slugs fail gracefully

Initial public report templates:

- `best-cities-early-career-ai-careers`
- `top-product-management-markets`
- `hidden-tech-hubs-new-graduates`

Batch 19B reports are conservative public artifacts. They feature markets from
existing public priority-market vocabulary and shared freshness/confidence
language. They do not calculate benchmark scores, index scores, recommendation
rankings, or new market coverage conclusions.

Excluded:

- benchmark/index scoring
- hidden report ranking formulas
- new recommendation authority
- new market coverage authority
- refresh, ingestion, or source-quality authority changes
- billing, institutional permissions, personalization, or export integration
  changes

Batch 19B is complete when:

- `/public/reports` returns a public-safe report list
- `/public/reports/{slug}` returns public-safe report details or a safe 404
- `/reports` renders the public report listing
- `/reports/:slug` renders report detail pages for the initial report family
- every public report exposes methodology, limitations, freshness, confidence,
  warnings, and public-safe source/provenance summary
- tests and validation confirm the public-report boundary

## Batch 19C - Owned Benchmark / Index Infrastructure

Batch 19C implements public benchmark/index infrastructure for recurring
category-defining indices.

Included:

- public benchmark payload contracts and validation
- a static public benchmark registry for the initial index family
- read-only public API routes for listing and retrieving public benchmarks
- frontend benchmark listing and detail pages
- benchmark cards, score-display tables, subscore tables, methodology blocks,
  limitations, freshness/confidence badges, warnings, source/provenance
  summaries, and related links
- tests proving benchmark templates exist, score/subscore bounds are enforced,
  required disclosures are present, internal-only fields are rejected,
  demo-safe/low-confidence labeling is present, public routes render, and
  unknown slugs fail gracefully

Initial public benchmark templates:

- `early-career-tech-access-index`
- `ai-career-geography-index`
- `product-career-market-index`

Batch 19C benchmarks are conservative public artifacts. They package public
category language, existing public priority-market vocabulary, and shared
freshness/confidence language. Numeric values are demo-safe score-display
examples, not production benchmark scores, recommendation rankings, or market
coverage conclusions.

Excluded:

- production benchmark/index scoring
- hidden benchmark formula weights
- new recommendation authority
- new market coverage authority
- refresh, ingestion, or source-quality authority changes
- billing, institutional permissions, personalization, or export integration
  changes

Batch 19C is complete when:

- `/public/benchmarks` returns a public-safe benchmark list
- `/public/benchmarks/{slug}` returns public-safe benchmark details or a safe
  404
- `/benchmarks` renders the public benchmark listing
- `/benchmarks/:slug` renders benchmark detail pages for the initial index
  family
- every public benchmark exposes methodology, limitations, freshness,
  confidence, warnings, score-display caveats, subscores, market explanations,
  market warnings, and public-safe source/provenance summary
- tests and validation confirm the public-benchmark boundary

## Batch 19D - SEO / Public Content Engine

Batch 19D implements structured public SEO/content pages for opportunity
geography and career market intelligence.

Included:

- a typed frontend public SEO/content registry
- a public guide listing page
- public route families for best-cities, city comparison, city career-market,
  and role market pages
- SEO metadata payload fields for title, description, canonical path, and topic
  tags
- confidence/freshness badges, methodology, limitations, warnings, category
  language, related reports, related benchmarks, and related public links
- tests proving required pages exist, required disclosures are present, related
  reports/benchmarks target known Layer 19 routes, all pages render, and unknown
  slugs fail gracefully

Initial public SEO/content pages:

- `best-cities-product-managers`
- `best-cities-ai-jobs`
- `best-cities-tech-internships`
- `nyc-vs-seattle-tech-careers`
- `austin-vs-atlanta-product-jobs`
- `atlanta-product-management-market`
- `seattle-ai-careers-market`
- `cybersecurity-entry-level-markets`

Route strategy:

- `/career-market-guides`
- `/best-cities/:slug`
- `/compare/:slug`
- `/career-markets/:slug`
- `/roles/:slug`

Batch 19D pages are conservative public explanation surfaces. They use Layer 19
vocabulary and link to public report/benchmark artifacts, but they do not create
production rankings, new scoring formulas, new coverage conclusions, or hidden
recommendation authority.

Excluded:

- production SEO-generated scoring or rankings
- DB-backed SEO content storage
- backend public-content APIs
- new recommendation authority
- new market coverage authority
- refresh, ingestion, or source-quality authority changes
- billing, institutional permissions, personalization, or export integration
  changes

Batch 19D is complete when:

- the public guide listing renders
- every initial SEO/content page renders through its route family
- every page exposes confidence, freshness/content period, methodology,
  limitations, warnings, related reports, related benchmarks, and category
  language
- unknown SEO/content slugs render a graceful not-found state
- tests and validation confirm the public-content boundary

## Batch 19E - Authority, Citation, Share, and Closeout Audit

Batch 19E completes Layer 19 by making public report, benchmark, and
SEO/content surfaces citable, shareable, and institution-ready without changing
any authority layer.

Included:

- suggested citation fields and rendering for public reports and benchmarks
- share-summary fields and rendering for public reports, public benchmarks, and
  public SEO/content guides
- source-authority labels that disclose demo-safe, low-confidence,
  methodology-backed, and non-production-ranking posture
- lightweight institutional CTA presentation hooks for public planning and
  advising use cases
- final closeout documentation and Layer 19 boundary audit
- tests proving the authority surfaces render and stay public-safe

Batch 19E authority surfaces are presentation metadata. They do not create
production scoring truth, benchmark scoring authority, market coverage
authority, recommendation authority, refresh/data-quality authority, billing
logic, institutional permissions, personalization behavior, or export
integrations.

Batch 19E is complete when:

- public report details render citation, share summary, source authority, and
  institutional-use blocks
- public benchmark details render citation, share summary, source authority,
  and institutional-use blocks
- public SEO/content guide details render share summary, source authority,
  suggested citation, and institutional-use blocks
- citation/share/source-authority payloads remain public-safe and strict
- unknown report, benchmark, and guide slugs still fail gracefully
- docs include the final closeout audit and lock-ready decision

## Future Slices

Potential future slices must preserve existing authority boundaries.

- Future post-Layer-19 work must be opened as a new layer or explicitly scoped
  follow-up batch with the same boundary audit standard.

## Completion Criteria

Batch 19A is complete when:

- category vocabulary is documented in `docs/CATEGORY_LANGUAGE.md`
- Layer 19 purpose, boundaries, slices, and completion criteria are documented
- public report methodology and benchmark methodology foundations exist
- public glossary and methodology routes render if frontend public routing
  exists
- tests prove documentation artifacts exist and public pages render
- validation has been run and any failures are documented
- no report rankings, benchmark scoring, or cross-layer authority changes were
  added
- Batch 19B public report infrastructure is lock-ready
- Batch 19C public benchmark/index infrastructure is lock-ready
- Batch 19D SEO/content guide infrastructure is lock-ready
- Batch 19E citation, share, source-authority, CTA, and closeout audit surfaces
  are lock-ready
- all applicable public artifacts preserve methodology, limitations, freshness,
  confidence, warnings, and public-safe source/provenance or authority labels
- demo-safe and low-confidence artifacts are labeled clearly
- final validation has been run and any unrelated failures are documented
