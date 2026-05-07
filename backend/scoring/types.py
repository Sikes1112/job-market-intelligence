"""Region-scoring constants.

Keeps the small, slow-moving symbols that other scoring modules need to
share. Weights and caps live in :mod:`backend.scoring.rulesets` so the
ruleset can be swapped at service construction.
"""

from __future__ import annotations

# Default version label for the bundled MVP ruleset. Stored on
# ``RegionMarketScore.score_ruleset_version``.
DEFAULT_SCORE_RULESET_VERSION: str = "marketscore_v1"
