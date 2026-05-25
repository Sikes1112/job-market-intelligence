"""Exceptions for structural provenance binding."""

from __future__ import annotations


class SourceRefNotFound(KeyError):
    """Raised when a source reference cannot be found."""


class SourceObservationNotFound(KeyError):
    """Raised when a source observation cannot be found."""


class ProvenanceBindingRequired(ValueError):
    """Raised when a fact link lacks the required source observation binding."""
