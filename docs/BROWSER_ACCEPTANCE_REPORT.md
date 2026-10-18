# Job Market Intelligence — Browser Acceptance Report

> **Historical baseline:** This report predates the final eight-market portfolio fixture and recommendation-integrity remediation. Its 4-opportunity/21-company inventory is not the current seed count. Use the root README and portfolio evaluation for current claims.

**Test date:** 2026-10-16 (America/New_York)
**Verdict:** `BROWSER_ACCEPTANCE_PASS_WITH_LIMITATIONS`

After the remediations listed below, the principal anonymous and locally authenticated workflows complete successfully against the real Vite frontend, FastAPI backend, disposable SQLite database, and bundled demonstration data. All 66 discovered canonical route templates were opened in Safari. Of 202 meaningful control groups inventoried, 193 were exercised; the remaining nine are destructive/security-sensitive or depend on intentionally unavailable external, billing, operator, or institutional configuration.

The count treats each form field, selector, action, disclosure, and materially different navigation action as one control group. Repeated instances of the same site-wide navigation or shared export component are counted once, while distinct selector values that alter behavior were all exercised.

## A. Runtime verification

### Environment and startup

The documented local architecture was used:

- Frontend: Vite at `http://127.0.0.1:5173`
- Backend: FastAPI/Uvicorn at `http://127.0.0.1:8000`
- Database: isolated `/tmp/jmi-browser-acceptance-retest.db`
- Authentication: existing `VITE_LOCAL_AUTH=true` development mode for authenticated testing; frontend restarted without that flag for anonymous testing
- Browser automation: real Safari UI driven through native accessibility/browser control, with desktop and Safari Responsive Design Mode at 390 × 844

Commands used:

```bash
APP_ENV=local .venv/bin/python -m scripts.seed_demo \
  --database-url "sqlite:////tmp/jmi-browser-acceptance-retest.db"

APP_ENV=local DATABASE_URL="sqlite:////tmp/jmi-browser-acceptance-retest.db" \
  .venv/bin/python -m scripts.beta_reference_data bootstrap --as-of 2026-07-09

APP_ENV=local DATABASE_URL="sqlite:////tmp/jmi-browser-acceptance-retest.db" \
  .venv/bin/uvicorn backend.api.app:app --host 127.0.0.1 --port 8000

cd frontend
VITE_LOCAL_AUTH=true npm run dev -- --host 127.0.0.1 --port 5173
```

The repository documents Python 3.11 and Node 22. The available machine ran Python 3.14.3, Node 24.13.0, and npm 11.6.2. This is an environment deviation, not an application failure; fresh migration, seed, startup, browser operation, build, and focused regressions succeeded on the available versions.

### Sample-data status

The fresh database applied all 46 migrations and loaded both the MVP seed and optional eight-market bootstrap. Direct database inventory, used only to establish the fixture baseline before browser testing, showed:

| Fixture | Count / values |
|---|---|
| Regions | 8: Atlanta, Austin, Chicago, Greater Boston, Greater NYC, Greater Seattle, San Francisco Bay Area, Washington DC |
| Companies | 21 |
| Marketplace opportunities | 4 |
| Current opportunities | 4 |
| Source/provenance references | 41 |
| Opportunity coverage contracts | 4 |

Browser pages consistently labeled the data as demo, synthetic, partial, heuristic, stale, or unverified where appropriate. Synthetic `.example` application URLs were shown as unverified and excluded, not as live employer application destinations.

### Runtime observations

- Final recommendation retest: every one of the seven goal modes returned ranked regions, ranked companies, and a strategy plan. Corresponding `POST /recommendations/strategy` requests returned 200 after the fixes.
- Final browser-console inspection found no new uncaught JavaScript exception. Two 403 responses for `/me/alerts` were expected free-plan entitlement denials and were surfaced in the UI.
- Expected optional-data 404s were rendered as unavailable/empty advanced analysis rather than breaking navigation.
- The pre-fix console captured the Career Identity exception described as D4 below. Pre-fix server logs also captured the 401, 422, and 400 failures used to diagnose D5, D6, and D9–D11.
- Browser Back and Forward restored Boston detail and the Boston/San Francisco comparison URL state correctly.

## B. Route and control coverage matrix

### Public routes

| Route / screen | Mode | D/T | Controls identified and interactions exercised | Result / evidence |
|---|---:|---:|---|---|
| `/` | Anonymous | 4/4 | Enter demo, public navigation, disclosure/source links, beta-feedback dialog; submitted a disposable local feedback record and received “Thanks—feedback sent.” | PASS |
| `/benchmarks` | Anonymous | 2/2 | Benchmark cards and navigation; opened a benchmark detail. | PASS |
| `/benchmarks/:benchmarkSlug` | Anonymous | 2/2 | Evidence/disclosure expansion and return navigation. | PASS |
| `/data-standards` | Anonymous | 3/3 | Governance disclosure, report form, navigation; submitted an information-quality report and observed queued recheck status. | PASS |
| `/data-licensing` | Anonymous | 1/1 | Licensing/document navigation. | PASS |
| `/developers` | Anonymous | 2/2 | Documentation index and API-topic links. | PASS |
| `/developers/docs` | Anonymous | 2/2 | Topic navigation and return to developer index. | PASS |
| `/developers/docs/authentication` | Anonymous | 1/1 | Documentation navigation/content. | PASS |
| `/developers/docs/errors` | Anonymous | 1/1 | Documentation navigation/content. | PASS |
| `/developers/docs/rate-limits` | Anonymous | 1/1 | Documentation navigation/content. | PASS |
| `/developers/docs/freshness-confidence` | Anonymous | 1/1 | Documentation navigation/content. | PASS |
| `/developers/docs/region-scores` | Anonymous | 1/1 | Documentation navigation/content. | PASS |
| `/developers/docs/company-geography` | Anonymous | 1/1 | Documentation navigation/content. | PASS |
| `/developers/docs/early-career-access` | Anonymous | 1/1 | Documentation navigation/content. | PASS |
| `/developers/docs/hiring-concentration` | Anonymous | 1/1 | Documentation navigation/content. | PASS |
| `/developers/docs/market-comparisons` | Anonymous | 1/1 | Documentation navigation/content. | PASS |
| `/embed/region-comparison` | Anonymous | 2/2 | Embedded comparison state and linked market navigation. | PASS |
| `/embed/market-score-card` | Anonymous | 2/2 | Embedded score-card state and linked market navigation. | PASS |
| `/career-market-guides` | Anonymous | 2/2 | Guide cards and guide-detail navigation. | PASS |
| `/best-cities/:slug` | Anonymous | 1/1 | Representative SEO guide navigation. | PASS |
| `/compare/:slug` | Anonymous | 1/1 | Representative SEO comparison navigation. | PASS |
| `/career-markets/:slug` | Anonymous | 1/1 | Representative career-market guide navigation. | PASS |
| `/roles/:slug` | Anonymous | 1/1 | Representative role guide navigation. | PASS |
| `/forecasts` | Anonymous | 1/1 | Empty-state navigation; correctly reported that no forecast was emitted. | PASS |
| `/reports` | Anonymous | 2/2 | Report list and report-detail navigation. | PASS |
| `/reports/:slug` | Anonymous | 2/2 | Report evidence/disclosures and return navigation. | PASS |
| `/glossary` | Anonymous | 1/1 | Public navigation/content. | PASS |
| `/methodology` | Anonymous | 1/1 | Public navigation/content. | PASS |
| `/data-limitations` | Anonymous | 1/1 | Public navigation/content. | PASS |
| `/privacy` | Anonymous | 1/1 | Public navigation/content. | PASS |
| `/terms` | Anonymous | 1/1 | Public navigation/content. | PASS |
| `/sources` | Anonymous | 1/1 | Public navigation/content. | PASS |

### Product and authenticated routes

| Route / screen | Mode | D/T | Controls identified and interactions exercised | Result / evidence |
|---|---:|---:|---|---|
| `/markets` | Both | 13/13 | Search, goal editing, market markers/cards, selection, comparison, reset, map/list state, URL state, authenticated scoring; Boston and SF exercised. | PASS; S1, S4; D1 |
| `/markets/dashboard` | Authenticated | 1/1 | Legacy route/canonical navigation. It resolves to the supported product shell rather than a distinct durable screen. | PASS (alias behavior) |
| `/markets/my-search` | Authenticated | 7/7 | Priority, saved comparison, pursuit, generated actions, completion, application, application status. | PASS |
| `/markets/my-search/pursuits/:id` | Authenticated | 4/4 | Open saved pursuit, generate actions, complete action, open tracked application. | PASS |
| `/markets/my-search/applications/:id` | Authenticated | 3/3 | Load persisted record, change to Applied, return navigation. | PASS |
| `/markets/profile` | Authenticated | 8/8 | Role, stage, work arrangement, preferred region, consent, save, reload, downstream personalized ranking. | PASS |
| `/markets/intelligence` | Authenticated | 5/5 | Goal mode, market selection, pairwise comparison, ranked cards, evidence display; AI/ML goal changed ranking. | PASS |
| `/markets/region/:id` | Both | 11/11 | Direct URL, company exploration, compare, explanation, save entitlement, CSV/PDF/Sheets/Notion/Airtable/ICS shared export component. | PASS; D6 |
| `/markets/company/:id` | Both | 5/5 | Direct URL, explanation, region navigation, save entitlement, return navigation. | PASS; S5; D2 |
| `/markets/compare` | Both | 6/6 | Region A/B selection, compare update, result inspection, snapshot save, prioritize, browser history. | PASS |
| `/markets/comparisons/:id` | Authenticated | 3/3 | Load saved snapshot, prioritize Boston, navigate back to comparison. | PASS |
| `/markets/discovery` | Authenticated | 8/8 | Regions, roles, industries, career stage/preferences, run, save entitlement, snapshot; Boston/SF produced Boston + Alphabet. | PASS |
| `/markets/career-identity` | Authenticated | 6/6 | Add fact, edit fact, save, version increment, reload persistence, error-boundary retest. | PASS; S3; D4 |
| `/markets/decisions` | Authenticated | 5/5 | Existing decision, add scenario, inspect options/recommendation, persistence, related navigation. | PASS |
| `/markets/recommendations` | Authenticated | 4/4 | Goal selector exercised across all seven modes, ranking disclosures, strategy sections, shared export component (validated on region screen). | PASS; S6; D9–D11 |
| `/markets/career-agent` | Authenticated | 6/6 | Ask/answer, action-plan generation, reminder preview, approve, audit/result, explicit no-external-runtime disclosure. | PASS; D5 |
| `/markets/opportunity-routes` | Both | 10/8 | Region, role, opportunity type, limit, include-unverified, generation, route details, relevant internal navigation. LinkedIn and Handshake manual external lookups not opened. | PASS WITH LIMITATION; U2–U3 |
| `/markets/current-opportunities` | Authenticated | 8/8 | Market/role/type filters, results update, reset, detail navigation, protected sign-in behavior, operations link. | PASS; D8 |
| `/markets/current-opportunities/:id` | Authenticated | 5/4 | Direct URL, synchronized scope, provenance/requirements, internal navigation; synthetic external `.example` destination intentionally not opened. | PASS WITH LIMITATION; S2; D3; U1 |
| `/markets/current-opportunities/operations` | Authenticated | 2/1 | Direct navigation and access explanation; operator refresh/mutation unavailable to the local non-operator identity. | INTENTIONALLY UNAVAILABLE; U4 |
| `/markets/policy` | Authenticated | 5/5 | Workforce, economic-development, education-alignment, peer, and report navigation. | PASS |
| `/markets/policy/regions/:id/workforce` | Authenticated | 2/2 | Region context and sibling-view navigation. | PASS |
| `/markets/policy/regions/:id/economic-development` | Authenticated | 2/2 | Region context and sibling-view navigation. | PASS |
| `/markets/policy/regions/:id/education-alignment` | Authenticated | 2/2 | Region context and sibling-view navigation. | PASS |
| `/markets/policy/regions/:id/peer-comparison` | Authenticated | 3/3 | Peer selection/display and sibling/report navigation. | PASS |
| `/markets/policy/reports/:region/:report` | Authenticated | 2/2 | Direct report URL and evidence/navigation. | PASS |
| `/markets/plans` | Both | 2/1 | Plan/features/reports inspected; checkout unavailable because billing backend is intentionally unconfigured. | INTENTIONALLY UNAVAILABLE; U5 |
| `/markets/institution` | Authenticated | 2/1 | Direct route and explicit no-organization explanation; organization-dependent workspace unavailable. | INTENTIONALLY UNAVAILABLE; U6; D7 |
| `/markets/institution/decisions` | Authenticated | 1/1 | Direct route and accurate no-organization state. | PASS (graceful degradation) |
| `/markets/institution/advisor` | Authenticated | 1/1 | Direct route and accurate no-organization/disabled-workspace explanation. | PASS (graceful degradation) |
| `/markets/institution/reports` | Authenticated | 1/1 | Direct route and accurate no-organization state. | PASS; D7 |
| `/markets/institution/data-requests` | Authenticated | 1/1 | Direct route and accurate no-organization state. | PASS; D7 |
| `/markets/institution/imports` | Authenticated | 1/1 | Direct route and accurate no-organization state. | PASS; D7 |
| `/markets/account` | Both | 11/8 | Anonymous explanation, local identity, preferences save, scoring overlay, export-user-data preview, entitlement states, protected navigation. API-client creation, preference deletion, and account deactivation were not executed. | PASS WITH LIMITATION; U7–U9 |

Route aliases `/markets/pricing`, `/markets/routes`, `/markets/opportunities`, `/markets/agent`, and `/markets/decision-workspace` parse to the canonical screens above and were not counted as additional route templates.

## C. Workflow results

| Workflow | Browser result |
|---|---|
| A — Geographic exploration | PASS. Started at Explore, selected Boston on the map, opened market detail, inspected employers/intelligence, navigated to HubSpot, and returned. Direct URLs and history restoration worked. The map focuses/zooms selected markets; no separate user-facing pan/zoom widgets or hover tooltip are implemented. |
| B — Market comparison | PASS. Selected Boston and San Francisco, inspected the comparison, changed a selection to Atlanta and back to Boston, saved a snapshot, prioritized Boston, and revisited the durable decision. |
| C — Job opportunity exploration | PASS WITH LIMITATION. Generated bundled marketplace routes, enabled unverified data, filtered four current opportunities, opened the HubSpot demo role, inspected provenance/requirements, submitted a quality report, and tracked a disposable application. Synthetic `.example` URLs remained explicitly unverified and were not opened. |
| D — Personalization | PASS. Local auth loaded without loops; profile/preferences saved and survived reload; preferred Boston, role, stage, and work arrangement influenced downstream displays. |
| E — Career Identity and decisions | PASS. Added and edited “Acceptance testing and QA,” observed version 7 → 8 and reload persistence, added a Boston-hybrid decision scenario, generated actions, completed an action, and revisited the saved records. |
| F — Additional functionality | PASS WITH INTENTIONAL LIMITATIONS. Recommendations, Career Agent, discovery, exports, local ICS reminders, user-data export, public reports/benchmarks/docs, data-quality reporting, policy views, and responsive navigation worked. Billing, institution, operator, and real external integrations degraded accurately. |

## D. Defects and minimum remediations

| ID | Severity | Defect and root cause | Minimum remediation / files | Browser retest |
|---|---|---|---|---|
| D1 | Major | First Explore load could return “Database unavailable.” React StrictMode issued duplicate concurrent evaluation POSTs, racing identity creation under SQLite uniqueness. | Deduplicated identical in-flight Explore evaluations in `frontend/src/ExplorePage.tsx`; added StrictMode regression in `ExplorePage.test.tsx`. | PASS on a fresh DB: eight markets rendered; one evaluation request; no 503. |
| D2 | Major | Local-auth users were treated as auth “unconfigured” by legacy product controls. | Local mode now reports configured in `frontend/src/auth.tsx`; regression in `localAuth.test.ts`. | PASS: company/protected actions render correct enabled or entitlement-gated state. |
| D3 | Major | Direct current-opportunity detail inherited unrelated default filter/coverage scope. | Synchronized absent URL filters to the detail record in `CurrentOpportunitiesPage.tsx`; added regression. | PASS: HubSpot detail shows Boston/product-management/job and matching limited coverage. |
| D4 | Major | Career Identity crashed on seed payloads missing `actionable_reason_codes`. | Null-safe rendering in `CareerIdentityPage.tsx`, optional type in `types.ts`, regression test. | PASS: add/edit/reload works; no exception. |
| D5 | Major | Career Agent answer requests bypassed the protected request helper and returned 401. | Added optional protected options in `api.ts`; passed them from `CareerAgentPage.tsx`; regression in `api.test.ts`. | PASS: answer, plan, preview, approve complete. |
| D6 | Major | Region “Explain guidance” sent forbidden `raw_total_score`, returning 422. | Filtered the raw field from the explanation packet in `App.tsx`; integration regression. | PASS for Boston and SF explanations. |
| D7 | Minor | Institution reports/imports/data-request screens showed disabled forms without explaining the missing organization. | Added explicit no-organization states in `App.tsx`. | PASS on all affected direct URLs. |
| D8 | Major | Anonymous protected-page “Sign in” buttons did nothing without Auth0/local auth. | Added an unavailable-auth notice route to Account in `auth.tsx`; regression test. | PASS: button navigates to a clear Auth0-not-configured explanation. |
| D9 | Major | Recommendations failed because company explanation warnings exceeded the 30-item response contract. | Stable dedupe/cap helper in `backend/recommendations/assembly.py`; regression in `test_recommendation_assembly.py`. | PASS for default goal. |
| D10 | Major | Strategy generation then exceeded the 50-item `evidence_warnings` contract. | Stable dedupe/cap in `backend/recommendations/strategy.py`; regression in `test_recommendation_strategy.py`. | PASS for default goal. |
| D11 | Major | Prestige mode exceeded the 25-item company-category evidence-reference contract. | Capped deduplicated category references in `backend/recommendations/strategy.py`; regression test. | PASS; all seven goal modes now render complete strategy output. |

No broad redesign, new product area, live provider, paid integration, or authentication weakening was introduced.

## E. Unverified functionality

| ID | Control not exercised | Reason |
|---|---|---|
| U1 | Open synthetic employer application URL | The seed uses `.example`; the UI correctly warns that it is not a real destination. |
| U2 | LinkedIn manual external search | External/manual destination, not an application-owned integration or core local workflow. |
| U3 | Handshake manual external lookup | External/manual destination, not an application-owned integration or core local workflow. |
| U4 | Operator refresh/mutation | Local identity lacks the required operator role; access denial is accurate. |
| U5 | Billing checkout | Billing provider is intentionally unconfigured; plans remain inspectable. |
| U6 | Institution organization actions | No institutional organization/membership is bundled; screens now explain this accurately. |
| U7 | Create API client | Creates persistent access credentials and was excluded from acceptance mutation scope. |
| U8 | Delete preferences | Destructive account action; not needed to establish the principal workflow. |
| U9 | Deactivate account | Destructive account action; not needed to establish the principal workflow. |

There is no unverified core anonymous exploration, comparison, local personalization, opportunity-detail, Career Identity, decision, or recommendation workflow.

## F. Evidence

The browser-control session captured the following real-browser screenshots inline with the acceptance run:

- **S1:** Desktop Boston Explore state with focused geography and market detail.
- **S2:** Current-opportunity detail showing synchronized Boston/product-management/job scope, provenance, and synthetic URL treatment.
- **S3:** Pre-fix Career Identity error boundary plus Safari console exception, retained as defect evidence for D4.
- **S4:** Anonymous Explore at 390 × 844 with usable reflow and mobile bottom navigation.
- **S5:** Company detail at 390 × 844 with readable content and reachable controls.
- **S6:** Repaired Recommendations screen in Safari with AI/cloud goal, partial-data disclosures, and no request failure.

Additional evidence includes the Safari accessibility snapshots for every route, the seven-goal recommendation sweep, browser history checks, and Uvicorn request logs. No video recording was produced.

Regression verification after the remediations:

- Frontend full suite: **274 passed across 41 files**
- Frontend lint: **passed**
- Frontend production build: **passed** (non-blocking existing large-chunk warning)
- Recommendation focused backend suite after final boundary fix: **26 passed**
- `git diff --check`: **passed**

The worktree contained substantial pre-existing uncommitted release-closeout work before this acceptance pass. It was preserved; no reset, commit, push, or publish action was performed.

## G. Final verdict

`BROWSER_ACCEPTANCE_PASS_WITH_LIMITATIONS`

- Route templates discovered: **66**
- Route templates visited: **66**
- Meaningful control groups discovered: **202**
- Meaningful control groups exercised: **193**
- Unverified/intentionally unavailable control groups: **9**
- Confirmed defects fixed and browser-retested: **11**

A user can clone the repository, seed the bundled data, start the real services, explore the eight-market demo, compare Boston and San Francisco, inspect companies and synthetic opportunities, personalize the experience with local authentication, save and revisit decisions/actions/applications, and use the major intelligence views without unexpected failures. The remaining limitations are explicit, non-core, and tied to intentionally absent external/billing/operator/institutional configuration or destructive/security-sensitive account actions.
