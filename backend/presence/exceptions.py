"""Presence service domain exceptions."""

from __future__ import annotations


class PresenceError(Exception):
    """Base for all presence service errors."""


class PresenceNotFound(PresenceError):
    """Raised when a presence_id (or company/region pair) is referenced but does not exist."""


class DuplicatePresence(PresenceError):
    """Raised when creating a presence whose presence_id already exists."""


class MissingCompanyForPresence(PresenceError):
    """Raised when the referenced company_id does not exist in the company table."""


class MissingRegionForPresence(PresenceError):
    """Raised when the referenced region_id does not exist in the region table."""


class InvalidPresenceEvidence(PresenceError):
    """Raised on documented evidence contradictions or otherwise invalid evidence."""
