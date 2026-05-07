"""Personalization service domain exceptions."""

from __future__ import annotations


class PersonalizationError(Exception):
    """Base for all personalization service errors."""


class InvalidPreferenceInput(PersonalizationError):
    """Raised on documented preference contradictions beyond Pydantic validation."""


class MissingRegionForPersonalization(PersonalizationError):
    """Raised when the preference payload references a region that does not exist."""
