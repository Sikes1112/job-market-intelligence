import json
import logging

from backend.config.settings import Settings, get_settings
from backend.shared.logging import JsonFormatter, configure_logging
from backend.shared.results import Err, Ok, Result


def test_ok_carries_value() -> None:
    result: Result[int] = Ok(42)
    assert result.is_ok is True
    assert result.is_err is False
    assert isinstance(result, Ok)
    assert result.value == 42


def test_err_carries_code_and_message() -> None:
    result: Result[int] = Err(code="NOT_FOUND", message="missing")
    assert result.is_ok is False
    assert result.is_err is True
    assert isinstance(result, Err)
    assert result.code == "NOT_FOUND"
    assert result.message == "missing"


def test_settings_have_documented_defaults() -> None:
    settings = Settings()
    assert settings.app_env == "dev"
    assert settings.log_level == "INFO"
    assert settings.service_name == "jmi-backend"


def test_get_settings_is_cached() -> None:
    assert get_settings() is get_settings()


def test_json_formatter_emits_structured_json() -> None:
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello %s",
        args=("world",),
        exc_info=None,
    )
    payload = json.loads(JsonFormatter().format(record))
    assert payload["level"] == "INFO"
    assert payload["logger"] == "test"
    assert payload["message"] == "hello world"


def test_configure_logging_installs_json_handler() -> None:
    configure_logging("DEBUG")
    root = logging.getLogger()
    assert root.level == logging.DEBUG
    assert len(root.handlers) == 1
    assert isinstance(root.handlers[0].formatter, JsonFormatter)
