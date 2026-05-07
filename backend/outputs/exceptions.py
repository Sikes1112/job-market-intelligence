"""Output assembly service domain exceptions."""

from __future__ import annotations


class OutputError(Exception):
    """Base for all output assembly errors."""


class OutputNotFound(OutputError):
    """Raised when an OutputMetadata row is referenced but does not exist."""


class MissingRegionForOutput(OutputError):
    """Raised when a region referenced by an output operation does not exist."""


class MissingCompanyForOutput(OutputError):
    """Raised when a company referenced by an output operation does not exist."""


class InvalidComparisonInput(OutputError):
    """Raised when a comparison input is malformed (wrong shape, identical IDs,
    blank IDs, etc.)."""


class InvalidOutputInput(OutputError):
    """Raised on documented output input contradictions beyond Pydantic validation."""
