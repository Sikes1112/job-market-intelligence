from __future__ import annotations

import logging
from typing import Any

from backend.shared.redaction import redact_sensitive


class ErrorMonitor:
    """Fail-open error-monitoring seam.

    No external provider is bundled. Production can attach an adapter with the
    same ``capture_exception`` method at ``app.state.error_monitor``.
    """

    def __init__(self) -> None:
        self._logger = logging.getLogger("backend.operations.errors")

    def capture_exception(self, exc: BaseException, *, context: dict[str, Any]) -> None:
        try:
            fields = redact_sensitive(
                {
                    **context,
                    "error_class": type(exc).__name__,
                }
            )
            self._logger.error("application_exception", extra={"extra_fields": fields})
        except Exception:
            pass


def capture_exception_fail_open(
    monitor: object | None,
    exc: BaseException,
    *,
    context: dict[str, Any],
) -> None:
    if monitor is None:
        return
    capture = getattr(monitor, "capture_exception", None)
    if capture is None:
        return
    try:
        capture(exc, context=context)
    except Exception:
        logging.getLogger("backend.operations.errors").debug(
            "error_monitoring_failed",
            extra={"extra_fields": {"error_class": type(exc).__name__}},
        )

