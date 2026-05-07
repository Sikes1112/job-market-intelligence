"""Geography service domain exceptions."""

from __future__ import annotations


class GeographyError(Exception):
    """Base for all geography service errors."""


class RegionNotFound(GeographyError):
    """Raised when a region_id is referenced but does not exist."""


class DuplicateRegion(GeographyError):
    """Raised when creating a region whose region_id already exists."""


class InvalidRegionHierarchy(GeographyError):
    """Raised on self-parenting, cycles, or missing parent references."""
