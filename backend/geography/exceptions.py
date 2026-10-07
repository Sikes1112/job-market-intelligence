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


class GeographicAliasConflict(GeographyError):
    """Raised when a normalized alias is already owned by another Region."""


class GeographicIdentityConflict(GeographicAliasConflict):
    """Raised when an ID, slug, or alias token belongs to another Region."""


class InvalidPublicSlug(GeographyError):
    """Raised when a public slug cannot be normalized to a safe token."""


class PublishedSlugImmutable(GeographyError):
    """Raised when an ordinary update attempts to replace a published slug."""


class GeographicResolutionError(GeographyError):
    """Base error for callers that require a resolved canonical Region."""


class GeographicInputUnknown(GeographicResolutionError):
    """Raised when a required geographic input is not known."""


class GeographicInputAmbiguous(GeographicResolutionError):
    """Raised when a required geographic input matches multiple Regions."""
