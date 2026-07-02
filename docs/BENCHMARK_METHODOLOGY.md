# Benchmark Methodology

This document defines the public methodology foundation for future opportunity
geography benchmarks. It explains how benchmark claims should be scoped and
disclosed before any future benchmark score is exposed.

Batch 19A does not create benchmark scoring, benchmark rankings, scoring
weights, formula versions, or new benchmark APIs. Batch 19C adds public
benchmark/index infrastructure for conservative public artifacts, but it still
does not create production benchmark scoring, hidden formula authority,
recommendation ranking, or new market coverage authority.

## Benchmark Purpose

A benchmark should compare career-market conditions within a clearly bounded
question. Examples:

- early-career access across regions
- company-region presence quality across markets
- regional opportunity density for a role family
- internship access visibility
- career-market signal strength across a stated data window

The benchmark purpose must be narrow enough that readers understand what is
being compared and what is outside scope.

## Eligibility And Scope

Future benchmarks should define:

- included geographies
- excluded geographies and why
- role families, industries, career stages, or employer groups in scope
- minimum coverage expectations
- data windows
- source categories
- missing-data treatment
- confidence requirements
- review and publication status

Benchmark scope should be visible before any comparative claim.

## Input Categories

Potential benchmark input categories may include:

- regional opportunity density
- company-region presence
- early-career access
- hiring activity signals
- internship or entry-level evidence
- sector concentration
- source freshness
- source diversity
- coverage quality
- career-market signal confidence

These categories are methodology placeholders in Batch 19A. They are not
weights, formulas, score components, or ranking rules.

## Batch 19C Initial Benchmark Family

Batch 19C introduces the first public benchmark/index templates:

- `early-career-tech-access-index`: Early-Career Tech Access Index
- `ai-career-geography-index`: AI Career Geography Index
- `product-career-market-index`: Product Career Market Index

These benchmarks are public index artifacts, not production scoring systems.
When real authorized benchmark inputs are not wired, benchmark payloads must be
demo-safe, low-confidence, and explicit that any score display values are not
production-grade truth.

## Public Benchmark Payload Rules

Every public benchmark payload must include:

- benchmark id, stable slug, name, category, and period
- summary and methodology summary
- limitations
- freshness date and freshness status
- confidence
- warnings
- ranked or featured market results
- score display fields
- subscores
- market-level explanation
- market-level warnings
- public-safe source/provenance summary when available
- related reports, benchmarks, or public pages where practical
- suggested citation metadata
- share summary metadata
- source-authority labels
- public presentation CTA metadata where appropriate

Public benchmark payloads must not expose internal-only fields such as raw
source IDs, private review notes, formula weights, production benchmark scores,
index score IDs, recommendation scores, or platform-internal scoring rows.

## Score Display Rules

Public benchmark pages may display score-like values only when the value is
clearly labeled with its basis.

Allowed score-display labels include:

- demo-safe display value
- public-safe summary value
- unavailable

Score display values and subscores must stay within `0..100` when numeric.
Demo-safe values must use low or unknown confidence, carry warnings, and state
that they are not production-grade truth. They must not imply live job-market
coverage, individualized advice, or current hiring certainty.

Featured order is editorial/template order unless an existing authorized
ranking source is explicitly cited. A public benchmark must never turn missing
market evidence into a negative opportunity claim.

## Citation, Share, And Source-Authority Rules

Batch 19E adds public authority surfaces for benchmark details.

Suggested citations must include only public-safe fields:

- source name
- benchmark title
- benchmark period
- product/category attribution
- public benchmark path
- access or freshness date

Suggested citations must not expose private source IDs, formula IDs, score-row
IDs, internal benchmark IDs beyond public slugs/paths, or unpublished source
references.

Share summaries must include the title, short category claim,
confidence/freshness label, one-sentence takeaway, public path, and a warning
when the benchmark is demo-safe or low-confidence. Share summaries are display
metadata only. They do not generate images, post to external channels, create
production benchmark rankings, or strengthen score authority.

Source-authority labels must disclose when a benchmark is demo-safe,
low-confidence, methodology-backed, and not production benchmark truth. They
should make score-display caveats obvious and must not imply that demo/static
values are authorized production scores.

Institutional CTA hooks may invite market comparison or student-placement
planning, but they are public presentation links only. They do not change
billing, institutional permissions, report-product access, recommendation
authority, market coverage authority, or data-export behavior.

## Public Benchmark Assembly Rules

Public benchmark builders may assemble public-safe language, public market
vocabulary, score-display labels, subscore labels, freshness labels, confidence
labels, warnings, limitations, and provenance summaries.

Public benchmark builders must not:

- calculate production benchmark or index scores
- create hidden formula weights
- bypass recommendation authority
- bypass market coverage authority
- bypass freshness, confidence, or provenance authority
- mutate platform-intelligence index, score, report, or ranking rows
- use fake precision for partial or demo-safe data

## Comparison Rules

Future benchmark explanations should:

- compare only markets with sufficient stated coverage
- disclose when a market is included as watchlist or partial coverage
- separate observed evidence from inferred signals
- preserve source freshness and confidence context
- distinguish "not observed" from "not present"
- explain why any market is excluded from comparison
- require human review before publication where benchmark claims are material

## Limitations

Benchmarks should never imply:

- exhaustive job-market coverage
- live job availability
- guaranteed interviews, offers, compensation, or career outcomes
- universal best-market conclusions for every person
- individualized advice
- absence of opportunity where data is merely incomplete

## Layer 19 Boundary

This benchmark methodology and the Batch 19C public benchmark infrastructure do
not:

- create production benchmark scoring
- create production benchmark rankings
- create hidden formula authority
- add benchmark report products
- add database tables
- alter core recommendation APIs
- change platform-intelligence calculations
- change recommendation ranking, market coverage, refresh, billing,
  institutional authority, or personalization

They only define public benchmark explanation posture, public-safe benchmark
payloads, and public rendering surfaces.
