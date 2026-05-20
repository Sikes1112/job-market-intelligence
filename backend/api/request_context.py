from __future__ import annotations

import re
from contextvars import ContextVar, Token
from uuid import uuid4

from starlette.datastructures import Headers
from starlette.types import Scope

REQUEST_ID_HEADER = "x-request-id"
REQUEST_ID_MAX_LENGTH = 128
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]+$")

_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)


def generate_request_id() -> str:
    return uuid4().hex


def is_safe_request_id(value: str | None) -> bool:
    if value is None:
        return False
    return (
        0 < len(value) <= REQUEST_ID_MAX_LENGTH
        and REQUEST_ID_PATTERN.fullmatch(value) is not None
    )


def resolve_request_id(inbound_request_id: str | None) -> str:
    if is_safe_request_id(inbound_request_id):
        return inbound_request_id
    return generate_request_id()


def request_id_from_scope(scope: Scope) -> str:
    state = scope.setdefault("state", {})
    request_id = state.get("request_id")
    if isinstance(request_id, str) and is_safe_request_id(request_id):
        return request_id

    request_id = resolve_request_id(Headers(scope=scope).get(REQUEST_ID_HEADER))
    state["request_id"] = request_id
    return request_id


def set_request_id(request_id: str) -> Token[str | None]:
    return _request_id.set(request_id)


def reset_request_id(token: Token[str | None]) -> None:
    _request_id.reset(token)


def get_request_id() -> str | None:
    return _request_id.get()
