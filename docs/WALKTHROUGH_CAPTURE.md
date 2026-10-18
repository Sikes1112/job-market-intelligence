# Real-product walkthrough capture plan

This repository does not bundle a video. The application can be recorded locally without external services by following this 60–90 second sequence against the portfolio seed. The sequence uses actual React, FastAPI, and SQLite behavior; it does not require mocked screens or edited results.

## Preparation

1. Follow the root README through migration, portfolio seeding, and startup.
2. Open `http://127.0.0.1:5173/markets` at a 1440-pixel desktop width.
3. Use the explicit seeded local reviewer identity. Close developer tools and hide local paths, terminal windows, notifications, and unrelated browser chrome.
4. Confirm the page states that the eight-market data and opportunities are synthetic demonstration evidence with simulated freshness.

## Capture sequence

| Time | Screen and action | Reviewer takeaway |
|---|---|---|
| 0–12 s | **Explore:** select Greater Boston and open its employer/opportunity context. | The product begins with geographic labor-market exploration, not a generic job feed. |
| 12–25 s | **Opportunities:** show Boston + software engineering + jobs, then select the hybrid work-arrangement filter and reset it. | Governed illustrative opportunities are useful, filterable, and explicitly not live openings. |
| 25–38 s | **Compare:** compare Greater NYC, Greater Boston, and Washington, DC; briefly reveal the differentiators and confidence qualification. | User-selected alternatives produce an evidence-aware comparison without claiming proximity or travel-time analysis. |
| 38–55 s | **Recommendations:** switch from entry-level access to AI/cloud access and show the changed ranking/strategy before opening the evidence disclosure. | Seven deterministic goals change the ranking while confidence, evidence, and limitations remain inspectable. |
| 55–67 s | **Career Identity:** show the populated synthetic reviewer profile and its personalization readiness. | Personalization is user-owned and optional; a fresh identity is not silently populated. |
| 67–85 s | **Decisions:** open the seeded San Francisco/Seattle/Austin decision, show the selected alternative and three persisted next actions. | The workflow carries intelligence into a versioned decision and action record. |

## Capture integrity

- Record the running application; do not substitute design mockups or generated imagery.
- Keep the synthetic-data, limited-coverage, and confidence language visible where it affects interpretation.
- Do not describe the recommendations as trained machine learning, predictive hiring probability, or autonomous career advice.
- Do not follow reserved `.example` destinations as though they were employer application sites.
- If the seed date differs, state the chosen demonstration date rather than implying live freshness.

The six checked-in screenshots under `docs/assets/portfolio/` provide the static fallback for GitHub reviewers and correspond to this same scenario sequence.
