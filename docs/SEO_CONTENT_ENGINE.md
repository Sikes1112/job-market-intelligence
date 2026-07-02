# SEO Content Engine

Layer 19D defines structured public content pages for Opportunity Geography
Intelligence and Career Market Intelligence. These pages are public explanation
surfaces, not production scoring surfaces.

## Page Families

The initial page families are:

- Best Cities pages
- City-vs-city comparison pages
- City career market pages
- Role market pages
- Methodology/glossary-linked pages

Initial pages:

- `best-cities-product-managers`
- `best-cities-ai-jobs`
- `best-cities-tech-internships`
- `nyc-vs-seattle-tech-careers`
- `austin-vs-atlanta-product-jobs`
- `atlanta-product-management-market`
- `seattle-ai-careers-market`
- `cybersecurity-entry-level-markets`

## Route Strategy

Batch 19D uses frontend-owned static public content because the existing public
glossary and methodology pages are frontend-owned, and there is no DB-backed
public content pattern.

Routes:

- `/career-market-guides`
- `/best-cities/:slug`
- `/compare/:slug`
- `/career-markets/:slug`
- `/roles/:slug`

The `/markets` route remains the product demo application route and is not used
for SEO city pages.

## Required Page Fields

Every public SEO/content page must include:

- id
- slug
- title
- page family/type
- summary
- canonical category language
- intended search intent
- content period or freshness date
- confidence
- methodology link or methodology summary
- limitations
- warnings
- primary sections
- related reports
- related benchmarks
- related glossary or methodology links
- suggested citation metadata
- share summary metadata
- source-authority labels
- institutional CTA presentation metadata where appropriate
- SEO metadata: title, description, canonical path, and topic tags

## Quality Rules

Public SEO/content pages must:

- use Layer 19 vocabulary consistently
- expose confidence and freshness/content period near the title
- show methodology, limitations, and warnings
- link to known public report and benchmark routes where relevant
- distinguish featured examples from production rankings
- treat missing evidence as unknown, not absence of opportunity
- use cautious public language such as "signals suggest" and "useful to inspect"

Public SEO/content pages must not:

- create generic blog spam
- invent production rankings
- imply live job availability
- create hidden scoring formulas
- bypass public report or public benchmark assets when linking to Layer 19
  artifacts
- bypass recommendation, market coverage, refresh, confidence, or provenance
  authority
- make individualized career advice claims

## Confidence And Freshness

Batch 19D pages are demo-safe and low-confidence unless a later authorized
source changes that posture.

Every page must show:

- confidence label
- content period or freshness date
- demo-safe warning when data is not production-grade
- limitations explaining coverage, current-source, and interpretation caveats

## Related Assets

Related reports must target known `/reports/:slug` pages from Batch 19B.
Related benchmarks must target known `/benchmarks/:slug` pages from Batch 19C.
Related methodology and glossary links may target public pages such as
`/methodology`, `/glossary`, `/data-limitations`, `/reports`, and `/benchmarks`.

Related links are navigation and explanation aids. They are not scoring
evidence and do not create ranking authority.

## Authority, Share, And Anti-Spam Rules

Batch 19E adds public authority surfaces to guide detail pages.

Guide pages should render:

- source-authority labels for demo-safe, low-confidence, methodology-backed,
  and non-production-ranking posture
- a compact share summary with title, category claim, confidence/freshness
  label, takeaway, public path, and warning
- a suggested citation that uses the public guide path, public period, and
  freshness date
- lightweight institutional CTA copy for advising, planning, and placement
  conversations

These surfaces are public presentation metadata only. They must not create
unsupported claims, hidden score formulas, production ranking truth, live job
availability claims, or institutional access behavior.

Guide copy must remain specific to career market intelligence and opportunity
geography. It should link to known public report and benchmark routes where
those artifacts are relevant, but those links are context and navigation, not
ranking evidence. Pages that are demo-safe or low-confidence must continue to
say so directly.

## Boundary

Layer 19D may define and render public SEO/content pages only.

Layer 19D must not:

- create production scoring logic
- create DB-backed SEO content storage
- modify recommendation authority
- modify market coverage authority
- modify refresh or data-quality authority
- modify billing, institutional permissions, personalization, or export
  integrations
