import json
import logging
import sys
from typing import Any

from backend.shared.redaction import redact_sensitive


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        extra = getattr(record, "extra_fields", None)
        if isinstance(extra, dict):
            payload.update(redact_sensitive(extra))
        if record.exc_info:
            payload["exc_info"] = redact_sensitive(self.formatException(record.exc_info))
        return json.dumps(redact_sensitive(payload), default=str)


def configure_logging(level: str = "INFO", *, service_name: str | None = None) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())
    if service_name:
        root.name = service_name
