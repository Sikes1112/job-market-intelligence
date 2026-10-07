from __future__ import annotations

import json
import logging
import sys

from backend.shared.logging import JsonFormatter
from backend.shared.redaction import REDACTED, redact_sensitive


def test_redact_sensitive_scrubs_nested_secret_fields_and_token_strings() -> None:
    redacted = redact_sensitive(
        {
            "Authorization": "Bearer raw-token-value",
            "profile": {
                "email": "person@example.com",
                "cookie": "sessionid=secret-cookie",
                "notes": ["safe", "postgresql://user:secret@example.test/db"],
            },
            "provider": {
                "api_key": "sk_live_secret",
                "webhook_secret": "whsec_secret",
            },
        }
    )

    assert redacted["Authorization"] == REDACTED
    assert redacted["profile"]["email"] == "person@example.com"
    assert redacted["profile"]["cookie"] == REDACTED
    assert redacted["profile"]["notes"] == ["safe", REDACTED]
    assert redacted["provider"]["api_key"] == REDACTED
    assert redacted["provider"]["webhook_secret"] == REDACTED


def test_json_formatter_redacts_extra_fields_and_exception_text() -> None:
    formatter = JsonFormatter()
    try:
        raise RuntimeError("database failed postgresql://user:secret@example.test/db")
    except RuntimeError:
        exc_info = sys.exc_info()
        record = logging.LogRecord(
            name="jmi.test",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="request failed",
            args=(),
            exc_info=exc_info,
        )
    record.extra_fields = {
        "authorization": "Bearer raw-token-value",
        "nested": {"cookie": "sessionid=secret-cookie"},
    }

    payload = json.loads(formatter.format(record))

    assert payload["authorization"] == REDACTED
    assert payload["nested"]["cookie"] == REDACTED
    assert payload["exc_info"] == REDACTED
    assert "secret" not in json.dumps(payload)
