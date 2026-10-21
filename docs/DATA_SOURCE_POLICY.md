# Data Source Policy

This is the active governance reference for market, employer, hiring, opportunity, and regional evidence. It defines which sources may support product facts and how provenance, missingness, and freshness are represented. The bundled portfolio data remains synthetic or curated demonstration material; it is not a maintained employment feed or verified market coverage.

## Evidence rules

- Every real observation needs a traceable source, observation date, usage rights, and enough context to reproduce its interpretation.
- Source observations do not become canonical product truth merely because they were ingested. Identity resolution, review, coverage, freshness, and display or ranking eligibility remain separate decisions.
- Missing data is not zero. `unknown`, `not_collected`, and `not_applicable` remain distinct from `zero_observed`, which requires a dated observed basis.
- Stale evidence remains stale; it must not be relabeled current, zero, or absent.
- Manual and user-submitted facts require reviewer, review time, source, and limitation metadata before they can support factual outputs.
- Aggregators may aid discovery only when the underlying observation and date remain traceable.
- Unverifiable claims, source-less snippets, and LLM-generated facts cannot serve as factual market evidence.

These rules are implemented through the shared provenance vocabulary, ingestion and review services, coverage contracts, and provenance audits under [`backend/shared/provenance.py`](../backend/shared/provenance.py), [`backend/ingestion/`](../backend/ingestion/), [`backend/imports/`](../backend/imports/), and [`backend/provenance/`](../backend/provenance/).

## Canonical vocabulary

Data origin:

- `demo_seed` and `synthetic_or_curated_demo`: deterministic or curated material for demonstrations and tests, never verified public coverage.
- `real_observed`: directly observed from an eligible source.
- `real_derived`: derived from one or more observed facts with lineage.
- `manual_reviewed`: accepted through documented human review.
- `unknown_origin`: origin is unresolved and cannot support a verified claim.

Value status:

- `unknown`: no supported value is known.
- `not_collected`: collection has not been attempted.
- `not_applicable`: the field does not apply.
- `zero_observed`: an eligible observation supports zero.
- `positive_observed`: an eligible observation supports a positive value.
- `stale`: the freshness window has expired.
- `conflicting`: eligible sources disagree.
- `low_confidence`: support is weak or has unresolved caveats.

## Source eligibility

| Source type | Default | Conditions |
|---|---|---|
| Company or program official | Allowed | Preserve the exact page and observation date. |
| Employer-linked ATS posting | Allowed | Employer identity, role, location, and posting context must be clear. |
| Government or public agency data | Allowed | Preserve release, period, geography, and methodology. |
| University or co-op board | Allowed | Preserve employer/program relationship and term or date. |
| Regional economic dataset | Allowed | Method, geography, date, and license must be documented. |
| Reputable aggregator | Caution | The original observation, date, and employer or dataset identity must be traceable. |
| Manual research or user submission | Review required | Record reviewer, date, source, and uncertainty before factual use. |
| LLM-generated or unknown source | Disallowed | May assist drafting or discovery but cannot establish a market fact. |

The same standard applies across the company universe, company-region presence, hiring activity, internships and co-ops, early-career programs, opportunities, and regional metadata. Ambiguous remote locations, duplicated postings, unclear program years, inferred office presence, or restricted datasets require review rather than automatic acceptance. A source with prohibited terms or missing usage rights must not be imported.

## Freshness and missingness

The implemented default windows in [`backend/shared/provenance.py`](../backend/shared/provenance.py) are:

| Evidence | Current for |
|---|---:|
| Company universe and presence | 180 days |
| Hiring counts | 14 days |
| Internships and co-ops | 120 days |
| Early-career programs | 90 days |
| Regional metadata | 365 days |

These are governance defaults, not promises that portfolio data is refreshed on those schedules. Domain-specific imports may define an additional documented staleness rule.

Count-like values must be classified before aggregation. `None` remains unknown or not collected; numeric zero is valid only with `zero_observed`; positive observations retain `positive_observed`. Score preparation may use supported available components, but it must not convert missing or stale inputs to zero. User-facing summaries should return a missing value and limitation rather than fabricate certainty.

## Provenance review

Diagnostic audits check for missing lineage, stale observations, source concentration, excessive low-confidence evidence, demo and real data mixed in one trust group, and missing values prepared as zero. Findings identify the affected evidence, severity, explanation, and remediation; they do not independently scrape sources, rewrite scores, or grant display authority.

Clean, clearly labeled demo data is allowed for deterministic product and test flows. It becomes a governance failure only when presented as real coverage or mixed into a real-evidence claim without preserving the distinction.
