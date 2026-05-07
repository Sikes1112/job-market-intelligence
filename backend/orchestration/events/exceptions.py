"""Slice 15 event/router exceptions.

Kept narrow. All routing failures surface as one of these. The router is a
pure function — it never logs, never persists. Callers that want to record
a failure handle it themselves.
"""

from __future__ import annotations


class EventValidationError(ValueError):
    """Raised when an event payload is structurally invalid for its type
    (missing required scope fields, wrong types, malformed pair, etc.)."""


class UnsupportedEventType(ValueError):
    """Raised when the router is asked about an :class:`EventType` it has
    no rule for. Slice 15 covers a fixed set; new event types are explicit
    additions, not silent fall-throughs."""
