"""Entry-level service domain exceptions."""

from __future__ import annotations


class EntryLevelError(Exception):
    """Base for all entry-level service errors."""


class EntryLevelNotFound(EntryLevelError):
    """Raised when an entry-level record is referenced but does not exist."""


class DuplicateEntryLevel(EntryLevelError):
    """Raised when creating an entry-level record whose entry_level_id
    already exists or whose (company_id, region_id) pair already has a
    record."""


class MissingHiringForEntryLevel(EntryLevelError):
    """Raised when no CompanyRegionHiring record exists for the pair."""


class InvalidEntryLevelInput(EntryLevelError):
    """Raised on documented input contradictions beyond Pydantic validation."""
