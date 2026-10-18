# Canonical Geographic Identity

Layer 41A establishes one geographic identity boundary for imports, APIs,
personalization, opportunities, decisions, saves, and frontend routing.

## Identity and persistence

`Region.region_id` remains the canonical internal identity. Existing IDs are
not renamed. Every supported market also has a stable, unique
`Region.public_slug` intended for public URLs and presentation-layer state.
Published slugs are compatibility contracts and must not be regenerated from a
display name. Ordinary Region updates may fill an unpublished null slug but
cannot replace a non-null published slug. Slugs are normalized once through
the shared lowercase ASCII/hyphen policy before persistence.

Inputs may be aliases; durable new relationships use canonical Region IDs.

An import `market_key` is an ingestion locator. It is registered as an alias
and must resolve to a Region before user-facing or durable domain data is
written. Historical JSON and saved references are interpreted at read or
adapter boundaries and are not rewritten merely to normalize geography.
The older priority-market expansion registry likewise contains planning keys
for both supported and not-yet-modeled candidates; those keys are compatibility
inputs, not replacements for the canonical Region ID emitted beside product
geography.

## Resolver and aliases

`GeographicResolver` is the only service-level translation boundary. It
accepts an exact Region ID, public slug, registered alias, legacy ID, import
key, or supported human-readable alias and returns either:

- a resolved canonical Region identity and resolution source;
- an explicit unresolved result; or
- an explicit ambiguous result with candidate Region IDs.

The returned identity includes the Region ID, public slug, display name, type,
state memberships, primary city, support status, and available focus metadata.
Callers that require a match can use the resolver's deterministic exceptions.
There is no fuzzy matching and ambiguous inputs are never guessed.

Lookup normalization applies Unicode NFKC and case folding, trims and
collapses whitespace, and treats runs of spaces, underscores, hyphens, slash,
comma, and period as separators. It intentionally does not expand arbitrary
abbreviations or remove all punctuation. Abbreviations such as `NYC` and
`DC/NoVA` are explicit aliases. Normalization supports lookup only; its output
is not a persistent geographic identifier.

Canonical Region IDs, public slugs, and aliases share one conflict-safe lookup
namespace after lookup normalization. A token may redundantly identify the
same Region through more than one form, but it cannot be owned by different
Regions. Conflicting writes are rejected transactionally, and the resolver
fails closed as ambiguous if historical/manual data violates that rule. Alias
categories record public slug, legacy ID, import key, city alias, alternate
name, or abbreviation without exposing that registry as canonical domain
truth.

## Metro, city, and state semantics

The Region is the product decision unit. A city can be a Region when the
repository has city-specific evidence; otherwise it can be a contextual alias
or `primary_city` of a metro Region. `parent_region_id` remains available for
genuine hierarchy but is not the authority for market/state membership.

`region_state_memberships` is the authoritative many-to-many market/state
association. State codes are two-letter uppercase US codes. A market can span
multiple states and a state can contain multiple markets without changing the
Region hierarchy.

`market_support_status` is explicit (`supported`, `unsupported`, or `unknown`).
A known but unsupported Region still resolves canonically; callers must not
present it as supported. Unknown and ambiguous text remains unresolved.

## Curated compatibility mapping

The versioned registry at `data/geography/curated_markets.json` owns the
supported-market slugs, aliases, primary cities, and state memberships. It is
applied idempotently by curated imports and by migration `0041`.

| Canonical Region ID | Public slug | Import key | States |
| --- | --- | --- | --- |
| `greater_boston` | `boston` | `boston` | MA |
| `greater_nyc` | `new-york` | `nyc` | NY, NJ, CT |
| `greater_seattle` | `seattle` | `seattle` | WA |
| `sf_bay_area` | `san-francisco-bay-area` | `san_francisco_bay_area` | CA |
| `washington_dc` | `washington-dc` | `washington_dc` | DC, VA, MD |
| `atlanta` | `atlanta` | `atlanta` | GA |
| `austin` | `austin` | `austin` | TX |
| `chicago` | `chicago` | `chicago` | IL |

Aliases include the known `greater_sf`, `dc_nova`, `greater_atlanta`, and
`greater_austin` legacy identifiers and the curated human-readable variants.
Punctuation variants such as `DC-NoVA` resolve through the documented lookup
normalization. No unresolved aliases are silently inserted into this registry.
`San Francisco` is currently a market-context alias for `sf_bay_area`, not a
claim that city and metro geography are universally interchangeable. The
shared namespace prevents a future city Region from publishing the conflicting
`san-francisco` slug until that alias is explicitly reassigned.

## Integration rules

- Current Opportunities preserve `market_label` and `location_text`. A
  canonical `market_id` is written only after resolution, with explicit
  resolution status and source. A provider-stable record may upgrade from
  unresolved to resolved geography, but weaker later evidence does not clear a
  resolved market or fragment the canonical opportunity. A confidently
  resolved different market is recorded as identity-conflict evidence for
  review rather than silently reassigning it. Canonical filtering never falls
  back to raw labels.
- Career Identity facts remain the authoritative, user-authored source. The
  personalization adapter records resolution metadata and uses canonical IDs
  only for recognized facts; it does not mutate facts.
- Decision scenario JSON remains historical. Comparison adapters resolve its
  legacy entries when safe. New Application geography is validated and stored
  as a Region FK.
- New Region saves and preferred-region writes either persist a resolved
  canonical Region ID or fail explicitly as unknown/ambiguous. Existing saved
  references can be resolved without destructive backfill.
- Region APIs emit canonical identity and metadata. `/regions/resolve` is a
  compatibility boundary: unknown is 404 and ambiguous is 409.
- Frontend URL builders prefer a canonical public slug when a full Region
  identity is available. Existing route tokens remain accepted and can be
  resolved by the API; React components do not own alias maps.

## Map-data boundary

Canonical Region data owns identity, state membership, primary city, support
status, and optional centroid/focus bounds. Simplified state geometry belongs
in a separately versioned static asset keyed by state code. Viewport,
selection, hover, zoom, and other map interaction state belong only in the
frontend.

The curated registry uses rounded U.S. Census Bureau Gazetteer representative
points as display proxies and leaves focus bounds null rather than fabricating
metro boundaries. The checked-in `us_states_simplified.geojson` is derived
from the public-domain U.S. Census Bureau 2024 Cartographic Boundary File.
`data/geography/README.md` records its source and rendering contract. This
static asset is not a second identity layer.

## SQLite upgrade integrity boundary

Fresh ORM-created SQLite schemas and PostgreSQL upgrades receive the declared
CHECK constraints. SQLite cannot add every CHECK to existing tables without a
destructive rebuild, so upgraded local/demo SQLite databases retain
application/Pydantic validation plus the existing indexes, foreign keys, and
unique constraints. Migration `0041` performs its cross-namespace conflict
preflight before any SQLite DDL. This is an explicit local/demo integrity
distinction, not permission for application writes to bypass validation.

## Known compatibility finding

Layer 36 `_market_fit` currently compares an average described elsewhere as a
normalized `[0,1]` score against `75` and `50`. Layer 41A does not use that
calculation for geographic resolution and does not change its historical
recommendation behavior. It remains assigned to the recommendation-authority
work where score semantics can be corrected coherently.
