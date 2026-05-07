"""Hiring service domain exceptions."""

from __future__ import annotations


class HiringError(Exception):
    """Base for all hiring service errors."""


class HiringNotFound(HiringError):
    """Raised when a hiring record is referenced but does not exist."""


class DuplicateHiring(HiringError):
    """Raised when creating a hiring record whose hiring_id already exists or
    whose (company_id, region_id) pair already has a record."""


class MissingPresenceForHiring(HiringError):
    """Raised when no CompanyRegionPresence record exists for the pair the
    hiring refresh is targeting."""


class InvalidHiringPair(HiringError):
    """Raised when a presence record exists but its presence_status indicates
    the pair is not eligible for hiring tracking (e.g. ``not_present``)."""


class InvalidHiringInput(HiringError):
    """Raised on documented input contradictions beyond Pydantic validation."""
