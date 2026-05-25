# Data Source Policy

Layer 3 is the Data Provenance and Trust Layer. This Batch 3A policy defines
the canonical vocabulary and source acceptability rules that must be in place
before importing real market data. It is policy only: it does not introduce
provenance tables, ingestion, scraping, API behavior, audit enforcement, or
score algorithm changes.

## Core Semantics

Seed/demo data is not factual public market coverage. Curated demo values may
be useful for UI development, local testing, examples, and deterministic demo
flows, but they must not be presented as verified market facts.

Real market facts require provenance in later Layer 3 batches. Until those
batches exist, real observed or real derived market facts must remain out of
the application data path unless they can be represented with the future
provenance schema and review workflow.

Missing data must not be interpreted as zero. `unknown`, `not_collected`, and
`not_applicable` are distinct from `zero_observed`. A zero requires an observed
basis, such as a dated source that was checked and found no matching count,
posting, program, or presence.

Stale data must remain distinguishable from current data. A fact that once had
an observed basis can become stale without becoming false, zero, or unknown.

Third-party aggregators may be useful discovery aids, but they require caution
unless source provenance is clear enough to trace the underlying observation.
User-provided or manually entered facts require review metadata, including who
reviewed the fact, when it was reviewed, what source was inspected, and any
limits or uncertainty noted during review.

Unverifiable claims, scraped snippets without source context, and LLM-generated
facts are disallowed as factual market evidence.

## Canonical Data Origin Vocabulary

- `demo_seed`: deterministic seed/demo data.
- `synthetic_or_curated_demo`: synthetic or manually curated demo values used
  for UI/testing.
- `real_observed`: a fact directly observed from an acceptable source.
- `real_derived`: a fact derived from one or more observed facts.
- `manual_reviewed`: a fact accepted after documented human review.
- `unknown_origin`: origin has not been established and must not be treated as
  verified market data.

## Canonical Value Status Vocabulary

- `unknown`: value is unknown.
- `zero_observed`: observed basis supports a zero value.
- `positive_observed`: observed basis supports a positive value.
- `not_applicable`: field does not apply to the subject.
- `not_collected`: collection has not been attempted.
- `stale`: value has exceeded its freshness window.
- `conflicting`: acceptable sources disagree.
- `low_confidence`: value has weak support or unresolved caveats.

## Source Type Defaults

| Source type | Default acceptability | Notes |
| --- | --- | --- |
| `company_official` | `allowed` | Company careers pages, official locations pages, investor or press pages. |
| `ats_job_board` | `allowed` | Direct ATS-hosted postings when the employer relationship is clear. |
| `government_public_data` | `allowed` | Public datasets from government or public agencies. |
| `university_or_coop_board` | `allowed` | University internship, co-op, or early-career boards with clear posting context. |
| `regional_economic_dataset` | `allowed` | Public or licensed regional datasets with documented methods. |
| `reputable_third_party_aggregator` | `allowed_with_caution` | Useful when provenance is clear; otherwise requires caution or review. |
| `manual_research` | `manual_review_required` | Requires review metadata and source notes. |
| `user_submitted` | `manual_review_required` | Requires review metadata before becoming factual evidence. |
| `llm_generated` | `disallowed` | May assist drafting or summarization, but is not factual market evidence. |
| `unknown_source` | `disallowed` | Must be resolved before use as factual evidence. |

## Company Universe

| Acceptability | Sources |
| --- | --- |
| Allowed | Official company websites, public company registries, government public data, verified public datasets with documented methods. |
| Allowed with caution | Reputable third-party company databases or aggregators when source lineage and refresh date are visible. |
| Manual review required | Manually entered companies, user-submitted companies, companies imported from restricted datasets. |
| Disallowed | LLM-generated company lists, unverifiable lists, scraped snippets without source URL and context, sources with prohibited terms. |

## Company-Region Presence

| Acceptability | Sources |
| --- | --- |
| Allowed | Official office/location pages, company careers pages with location filters, public filings, government or regional datasets. |
| Allowed with caution | Third-party office/location aggregators, job boards implying presence only through postings. |
| Manual review required | Manually researched presence claims, user-submitted office claims, ambiguous remote/hybrid location evidence. |
| Disallowed | LLM-generated presence claims, unsupported social posts, snippets without source context, stale claims presented as current. |

## Hiring Activity

| Acceptability | Sources |
| --- | --- |
| Allowed | Company official careers pages, ATS job boards with employer identity, dated public job postings. |
| Allowed with caution | Reputable job aggregators when original posting source, posting date, and employer identity are clear. |
| Manual review required | Manual counts, user-submitted posting evidence, aggregator-derived counts with partial provenance. |
| Disallowed | LLM-generated hiring counts, undated snippets, duplicated postings without dedupe basis, unverifiable claims. |

## Internships

| Acceptability | Sources |
| --- | --- |
| Allowed | Company careers pages, ATS postings, university career boards, official internship program pages. |
| Allowed with caution | Third-party aggregators with source links and posting dates. |
| Manual review required | Manually entered internship availability, user submissions, program pages with unclear season/year. |
| Disallowed | LLM-generated internship claims, stale program pages presented as current, snippets without source context. |

## Co-ops

| Acceptability | Sources |
| --- | --- |
| Allowed | University co-op boards, official employer co-op postings, ATS postings explicitly identifying co-op roles. |
| Allowed with caution | Aggregators that preserve original employer or university source context. |
| Manual review required | Manual co-op classifications, user-submitted co-op claims, ambiguous internship/co-op labeling. |
| Disallowed | LLM-generated co-op claims, unsupported forum posts, scraped snippets without source context. |

## Early-Career Programs

| Acceptability | Sources |
| --- | --- |
| Allowed | Official company new-grad, rotational, apprenticeship, fellowship, or early-career program pages. |
| Allowed with caution | Third-party early-career program lists when original source and date are visible. |
| Manual review required | Manually curated program classifications, user-submitted program claims, pages with unclear active status. |
| Disallowed | LLM-generated program claims, stale program claims presented as active, unverifiable summaries. |

## Regional Metadata

| Acceptability | Sources |
| --- | --- |
| Allowed | Government public data, regional economic datasets, public university or workforce datasets, official statistical releases. |
| Allowed with caution | Reputable aggregators that cite methodology, source dates, and licensing terms. |
| Manual review required | Manually curated regional groupings, user-provided local corrections, restricted datasets. |
| Disallowed | LLM-generated regional facts, unverifiable rankings, snippets without source and date, prohibited-license material. |

## Freshness Windows

These windows are conservative defaults for determining when a fact should be
treated as current. They are intentionally easy to change when later Layer 3
batches add provenance schema and audit enforcement.

| Data type | Freshness category | Current for |
| --- | --- | --- |
| Company universe | `slow_changing` | 180 days |
| Company presence | `slow_changing` | 180 days |
| Hiring counts | `fast_changing` | 14 days |
| Internships/co-ops | `seasonal` | 120 days |
| Early-career programs | `medium_changing` | 90 days |
| Region metadata | `slow_changing` | 365 days |

Facts older than the window are stale, not zero. If no collection has happened,
the value is `not_collected` or `unknown`, not zero.

## Layer 3C Unknown/Zero and Freshness Handling

Count-like values must be classified before aggregation:

- `None` remains `unknown` or `not_collected`.
- `0` is `zero_observed` only when the value has an observed basis.
- Positive counts are `positive_observed`.
- Stale values remain `stale` and must not be reported as current zero.

Score-input preparation may use available observed components, but missing
components must be omitted or reported as unknown rather than converted to
zero. Output summaries should prefer `null` plus a warning over a fake zero
when any required count input is unknown, not collected, or stale.

Fact-link freshness uses the windows above. Score-input freshness must declare
the underlying source fact category, such as hiring counts or entry-level
programs, rather than using a generic score-level window.

## Layer 3D Provenance Audit Checks

Layer 3D adds diagnostic provenance audit checks. These checks return
structured findings and do not scrape, ingest, call external APIs, rewrite
scores, or block write paths.

The audit checks cover:

- missing provenance for expected real observed or real derived facts
- stale source observations based on the Layer 3 freshness windows
- single-source overreliance across too many real facts of the same binding type
- concentration of low-confidence observations
- demo/seed provenance mixed with real provenance for the same fact
- unknown, not-collected, or stale values prepared as numeric zero or
  `zero_observed`

Findings include a code, severity, affected fact/source identifiers when
available, explanation, recommended remediation, and whether the finding blocks
real-data trust. Clean demo seed data is allowed to remain demo-labeled and
does not fail the real-market provenance audit unless it is mixed into a real
trust group.
