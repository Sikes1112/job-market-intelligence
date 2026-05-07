"""Audit service domain exceptions."""

from __future__ import annotations


class AuditError(Exception):
    """Base for all audit service errors."""


class InvalidAuditScope(AuditError):
    """Raised when the scope payload supplied to the audit handler is malformed."""
