# Region Expansion Playbook

Layer 12 adds the backend/domain foundation for broader market coverage. A
region is not "covered" just because a row, workflow, or placeholder exists.
Coverage must move through staged validation and keep its current tier visible.

This playbook is the standard path for adding a market.

## Staged Path

1. Source collection
   - Collect candidate official, public, or licensed sources.
   - Record source type, data origin, license posture, collection date, and
     owner.
   - A source list alone does not make a region covered.

2. Company universe definition
   - Define the candidate company universe for the labor market.
   - Document inclusion and exclusion criteria.
   - A candidate company list is not validated regional presence.

3. Presence validation
   - Attach evidence that companies are meaningfully present in the region.
   - Preserve unknown, low-confidence, or unsupported presence separately.
   - Unvalidated presence must not drive confident coverage claims.

4. Hiring signal collection
   - Collect current hiring signals with observed-at timestamps.
   - Preserve unknown counts instead of treating them as zero.
   - Missing hiring signals keep the market partial or watchlist.

5. Entry-level signal collection
   - Collect internship, co-op, entry-level full-time, and formal early-career
     program signals when available.
   - General hiring strength is not entry-level coverage.

6. Freshness classification
   - Classify collected facts against the existing freshness windows.
   - Preserve stale, partial, and unknown states.
   - Unknown freshness cannot be presented as fresh.

7. Audit pass
   - Review provenance, source diversity, score components, region boundaries,
     warnings, and admin approval before release.
   - Audit approval is required before public confidence claims.

8. Frontend release
   - Expose the region only with its current coverage tier, warnings,
     freshness/source labels, and sector-specific coverage where known.
   - Frontend release does not upgrade a partial or placeholder market.

## Canonical Priority Markets

The canonical ordered priority market registry lives in
`backend/geography/market_coverage.py` as `PRIORITY_MARKETS`. The current order
is:

1. NYC
2. Seattle
3. Austin
4. DC / NoVA
5. Atlanta
6. Chicago
7. Los Angeles
8. Raleigh-Durham
9. Denver / Boulder
10. Boston
11. SF Bay Area
12. Dallas
13. Miami
14. Pittsburgh
15. Minneapolis

The existing region-expansion target candidate plan is derived from this
registry. Creating target candidates does not publish, approve, refresh-enable,
or claim full coverage for those markets.

## Coverage Tiers

Coverage tiers describe market research completeness, not opportunity quality.

- Tier 1 - fully covered market
  - Strong company universe
  - Presence validated
  - Hiring signals present
  - Entry-level signals present
  - Freshness acceptable
  - Multiple source types
  - Safe for confident market comparison

- Tier 2 - partial but useful market
  - Useful but incomplete coverage
  - Directionally useful for comparison
  - At least one signal class may be weaker or incomplete
  - Must be labeled as partial

- Tier 3 - watchlist / emerging market
  - Tracked for future expansion
  - Not enough for confident recommendations

- Tier 4 - placeholder only
  - Should not be presented as analyzed
  - Should not be ranked as a confident recommendation

## Sector Coverage

Region-level coverage and sector-specific coverage are separate. A region may
be Tier 2 overall but Tier 1 for AI, or Tier 1 overall but weak for fintech.
Sector coverage must not overwrite the overall region tier.

Canonical sector coverage categories:

- AI
- cloud
- cybersecurity
- fintech
- healthtech
- edtech
- enterprise SaaS
- public sector tech
- defense tech
- consumer tech

## Coverage Quality Score

`CoverageQualityScore` is a heuristic coverage-readiness model, not an
objective market score. Every component is bounded to `[0, 1]`, where zero means
absent or not demonstrated, not a negative market finding.

Components:

- company coverage
- hiring coverage
- entry-level coverage
- freshness
- source diversity
- confidence

The helper can calculate a simple average total and suggest a conservative tier,
but component detail must be preserved so partial coverage can be explained.
Declaring Tier 1 or Tier 2 requires a quality score, and a declared tier cannot
be stronger than the quality components support.
