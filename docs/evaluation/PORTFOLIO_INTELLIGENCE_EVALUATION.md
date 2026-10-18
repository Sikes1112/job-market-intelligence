# Portfolio Intelligence Evaluation

## Evaluation claim

This evaluation checks deterministic correctness and internal contract behavior against the governed portfolio fixture. It does not measure predictive accuracy, labor-market representativeness, user outcomes, or real employer demand.

## Reproducible authority

Run:

```bash
APP_ENV=test .venv/bin/pytest -q tests/integration/test_portfolio_demo_batch1.py
```

The executable golden scenarios live in [`tests/integration/test_portfolio_demo_batch1.py`](../../tests/integration/test_portfolio_demo_batch1.py). Focused edge cases live in the recommendation, market-intelligence, current-opportunity, Career Identity, and career-decision test modules.

## What is evaluated

| Property | Golden behavior |
|---|---|
| Canonical fixture | 8 markets, 20 employers, and 24 shared opportunity scenarios |
| Idempotency | A second seed produces no duplicate logical records or reviewer state |
| Source governance | All scenario links use `portfolio-demo.example`; synthetic provenance stays explicit |
| Opportunity eligibility | Active governed records are separated from closed, unsupported, experimental, and low-confidence exclusions |
| Missingness | Unknown hiring count remains `None/unknown`; observed zero remains `0/zero_observed` |
| Mode differentiation | Seven modes produce seven stable market-order signatures |
| Determinism | Repeating the same strategy request produces the same ranked signature |
| Goal-path independence | Different authenticated headers do not alter the public goal-based strategy response |
| Authenticated personalization | Two isolated, consented Career Identities produce different supported employer rankings and repeat deterministically |
| Consent and isolation | Missing/non-consented identity context is not labeled personalized; one user's facts do not appear in another user's metadata |
| Explainability | Top results contain reasons, evidence references, confidence, freshness, and synthetic warnings |
| Strategy behavior | Every mode yields justified actionable targets; a numerically leading watchlist result is distinguished from its actionable fallback |
| Contextual navigation | Frontend regression verifies that a personalized non-Boston market and supported role survive the opportunity transition and URL restoration |
| Scenario sensitivity | Boston defined search, selected-market comparison, and the authenticated flexible-graduate discovery path return different workflows/results |
| Clean-user isolation | Only the explicit local reviewer receives seeded identity and decision state |

## Golden mode results

| Goal mode | Expected top market |
|---|---|
| `maximize_entry_level_access` | `sf_bay_area` |
| `maximize_prestige` | `sf_bay_area` |
| `maximize_ai_cloud_concentration` | `greater_nyc` |
| `maximize_underrated_markets` | `greater_boston` |
| `maximize_internship_coop_access` | `sf_bay_area` |
| `maximize_lower_competition` | `austin` |
| `maximize_geographic_flexibility` | `greater_boston` |

These expectations are justified fixture contracts: they prove that changing a declared objective changes the result through real weights and evidence. They are not endorsements of those markets outside the synthetic demonstration.

For lower competition, Austin is the fixture's numerical leader but remains watchlisted; the strategy exposes a different supported fallback rather than presenting Austin as the action. The frontend regression in `RecommendationExperience.test.tsx` pins that distinction.

## Failure and abstention evidence

The broader test suite verifies:

- ranking-influence denial removes a payload from recommendation ranking;
- insufficient direct goal evidence can produce `not_supported` or abstention rather than a fabricated score;
- missing components remain recorded rather than becoming zero;
- weak confidence, freshness, coverage, missing data, or provenance can redirect a result to the watchlist;
- current opportunities without an eligible active source or usable coverage fail closed;
- stale Career Identity writes produce a version conflict;
- fresh identities remain empty and do not inherit the demonstration persona.

## Relationship to the earlier 40-case artifact

[`docs/implementation/layer_34c/artifacts/product_quality_evaluation_report.json`](../implementation/layer_34c/artifacts/product_quality_evaluation_report.json) is retained as a historical Layer 34 evaluation. It contains useful evidence about provisional and abstained market-goal combinations, but it predates the portfolio opportunity fixture and should not be presented as a current predictive benchmark.

The portfolio golden scenarios are stronger evidence for the current reviewer experience because they exercise the final seeded data, all seven public goal modes, governed opportunities, authenticated personalization, and persisted decisions. Focused API tests establish identity sensitivity, consent, determinism, and isolation for the `/me/discover/personalized` path. Neither artifact validates real-world recommendation usefulness.
