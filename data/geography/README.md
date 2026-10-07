# Geographic data boundary

`curated_markets.json` is the versioned identity and lightweight metadata
fixture used to reconcile the eight current curated import markets with
canonical `Region.region_id` values. Its state memberships are copied from the
existing curated import files. It intentionally contains no guessed centroid
or focus bounds.

Future state geometry belongs at `data/geography/us_states_simplified.geojson`
and must be keyed by two-letter state code, preserve Alaska and Hawaii, include
source/version/license documentation, and contain only simplified state
boundaries. Layer 41A does not add that asset because no suitably licensed,
source-controlled geometry exists in this repository. Database Regions remain
identity/metadata truth; state geometry is a versioned static rendering asset;
viewport and selection are transient frontend state.
