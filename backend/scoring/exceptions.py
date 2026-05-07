"""Region-scoring service domain exceptions."""

from __future__ import annotations


class ScoringError(Exception):
    """Base for all region-scoring service errors."""


class RegionScoreNotFound(ScoringError):
    """Raised when a region_score_id (or region) is referenced but missing."""


class MissingRegionForScoring(ScoringError):
    """Raised when the referenced region_id does not exist."""


class InvalidScoringInput(ScoringError):
    """Raised on documented input contradictions beyond Pydantic validation."""


class InvalidRuleset(ScoringError):
    """Raised when a :class:`ScoringRuleset` has structurally invalid weights or caps."""
