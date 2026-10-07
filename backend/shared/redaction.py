"""Reusable redaction helpers for logs and safe operational payloads."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

REDACTED = "[REDACTED]"

SENSITIVE_KEY_PARTS = (
    "authorization",
    "cookie",
    "password",
    "passwd",
    "secret",
    "token",
    "api_key",
    "apikey",
    "access_key",
    "credential",
    "database_url",
    "db_url",
    "dsn",
    "raw_key",
)


def redact_sensitive(value: Any) -> Any:
    """Return a JSON-safe copy with sensitive fields and strings redacted."""

    if isinstance(value, Mapping):
        redacted: dict[Any, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            redacted[key] = REDACTED if _sensitive_key(key_text) else redact_sensitive(item)
        return redacted
    if isinstance(value, str):
        return _redact_string(value)
    if isinstance(value, Sequence) and not isinstance(value, bytes | bytearray):
        return [redact_sensitive(item) for item in value]
    return value


def _sensitive_key(key: str) -> bool:
    normalized = "".join(
        character
        for character in key.casefold()
        if character.isalnum() or character == "_"
    )
    return any(part in normalized for part in SENSITIVE_KEY_PARTS)


def _redact_string(value: str) -> str:
    lowered = value.casefold()
    if "bearer " in lowered:
        return REDACTED
    if "authorization:" in lowered:
        return REDACTED
    if "cookie:" in lowered or "set-cookie:" in lowered:
        return REDACTED
    if "postgresql://" in lowered or "postgres://" in lowered:
        return REDACTED
    if any(prefix in value for prefix in ("sk_live_", "sk_test_", "whsec_", "jmi_live_")):
        return REDACTED
    return value
