# Geographic data boundary

`curated_markets.json` is the versioned identity and lightweight metadata
fixture used to reconcile the eight current curated import markets with
canonical `Region.region_id` values. Its state memberships are copied from the
existing curated import files. Market points use the U.S. Census Bureau 2024
Gazetteer incorporated-place representative latitude/longitude for the named
primary city, rounded to four decimals. These are explicitly point-display
proxies rather than claims about metro boundaries. Focus bounds remain null.

`us_states_simplified.geojson` contains the 50 states and District of Columbia
from the U.S. Census Bureau 2024 Cartographic Boundary File for states at
1:20,000,000. It is public-domain U.S. government data and is keyed by the
two-letter `state_code`. The source is
`https://www2.census.gov/geo/tiger/GENZ2024/kml/cb_2024_us_state_20m.zip`.
The frontend copy under `frontend/public/data/` is byte-equivalent so Vite can
serve it without a GIS runtime. Database Regions remain identity/metadata
truth; state geometry is a versioned static rendering asset; viewport and
selection are transient frontend state.
