# Public Report Methodology

This document defines the public methodology foundation for future Career
Market Intelligence reports. It explains what a public report must disclose
before a reader relies on its conclusions.

Batch 19A does not create report rankings, generate reports, publish new report
products, or change existing report APIs. Batch 19B adds public report
infrastructure for conservative report artifacts, but it still does not create
benchmark scoring, index scoring, recommendation ranking, or new market coverage
authority.

## Report Purpose

A public report should explain a specific career-market question, such as:

- where regional opportunity density appears stronger
- where company-region presence is visible
- where early-career access appears better supported
- how career-market signals changed across a stated data window
- what limitations make a finding directional rather than definitive

Reports should be framed as opportunity geography and career market
intelligence, not as exhaustive lists of open jobs.

## Required Public Disclosures

Every future public report should disclose:

- report purpose and intended audience
- geography and market scope
- company, sector, role-family, and career-stage scope where relevant
- data window and freshness posture
- source categories used
- coverage limitations and missing-data handling
- confidence posture and uncertainty language
- whether seeded demo data, inferred data, or partial imports are present
- limitations on interpretation
- independent verification guidance

## Batch 19B Initial Report Family

Batch 19B introduces the first public report templates:

- `best-cities-early-career-ai-careers`: Best Cities for Early-Career AI Careers
- `top-product-management-markets`: Top Product Management Markets
- `hidden-tech-hubs-new-graduates`: Hidden Tech Hubs for New Graduates

These reports are public report artifacts, not hidden scoring systems. Their
featured markets are drawn from existing public priority-market vocabulary and
must be labeled with low confidence when current ranked data is not available.

## Public Report Payload Rules

Every public report payload must include:

- report id, stable slug, title, category, and report period
- summary and intended public interpretation
- markets covered
- ranked or featured market results
- methodology summary
- limitations
- freshness date and freshness status
- confidence
- warnings
- public-safe source/provenance summary when available
- related reports, benchmarks, or related public pages where practical
- suggested citation metadata
- share summary metadata
- source-authority labels
- public presentation CTA metadata where appropriate

Public report payloads must not expose internal-only fields such as raw source
IDs, private review notes, formula weights, benchmark scores, index scores, or
recommendation scores.

When real ranked data is not available from existing authorized systems, public
reports must use conservative featured-market examples. Featured order is
editorial/template order unless an existing authorized ranking source is
explicitly cited. Demo-safe or low-confidence payloads must say so directly.

## Citation, Share, And Source-Authority Rules

Batch 19E adds public authority surfaces for report details.

Suggested citations must include only public-safe fields:

- source name
- report title
- report period
- product/category attribution
- public report path
- access or freshness date

Suggested citations must not expose private source IDs, formula IDs, review
notes, internal report IDs beyond public slugs/paths, or unpublished source
references.

Share summaries must be compact and cautious. They should include the title,
short category claim, confidence/freshness label, one-sentence takeaway, public
path, and a warning when the report is demo-safe or low-confidence. Share
summaries are UI/data support only; they do not generate images, post to social
channels, or create ranking claims.

Source-authority labels must disclose when a report is demo-safe,
low-confidence, methodology-backed, and not production ranking truth. They
should help readers understand the public evidence posture without implying
stronger source coverage than the payload actually contains.

Institutional CTA hooks may invite career-center or advising use, but they are
presentation links only. They do not change billing, institutional permissions,
report-product access, recommendation authority, or data-export behavior.

## Public Report Assembly Rules

Public report builders may assemble public-safe language, public market
vocabulary, freshness labels, confidence labels, warnings, limitations, and
provenance summaries.

Public report builders must not:

- calculate new benchmark or index scores
- create hidden ranking formulas
- treat related benchmark links as scoring evidence
- bypass recommendation authority
- bypass market coverage authority
- bypass freshness, confidence, or provenance authority
- turn missing market evidence into negative opportunity claims
- use fake precision for partial or demo-safe data

## Evidence Categories

Reports may explain evidence categories such as:

- company-region presence
- hiring activity signals
- early-career access signals
- internship and entry-level evidence
- regional opportunity density
- sector or role-family concentration
- market fit context
- source freshness and coverage metadata
- career-market signal strength

Evidence categories are descriptive methodology language in Batch 19A. They do
not create a new ranking system or scoring formula.

## Freshness, Coverage, And Confidence

Public reports should keep freshness, coverage, and confidence visible near
material claims.

- Freshness describes how recently evidence was observed or prepared.
- Coverage describes how complete or partial the evidence is for the stated
  market scope.
- Confidence describes how strongly the available evidence supports the public
  interpretation.

Unknown freshness, weak coverage, or low confidence must be disclosed as a
limitation rather than hidden behind stronger language.

## Public-Safe Language

Use:

- "signals suggest"
- "evidence indicates"
- "observed company-region presence"
- "directional market fit"
- "regional opportunity density"
- "coverage is partial"
- "not observed in available sources"

Avoid:

- "guarantees"
- "complete job market"
- "all open roles"
- "best city for every candidate"
- "no opportunity exists"
- "current hiring certainty"

## Layer 19 Boundary

This methodology foundation and the Batch 19B public report infrastructure do
not:

- create report ranking authority
- score benchmarks
- score indices
- create hidden report formulas
- alter core recommendation APIs
- change canonical scores, recommendation ranking, market coverage, refresh
  cadence, billing, institutional permissions, or personalization

They only define public report explanation posture, public-safe report payloads,
and public rendering surfaces.
