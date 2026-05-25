from __future__ import annotations

import base64
import json
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Any

from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.auth.jwks import SHA256_DIGEST_INFO_PREFIX
from backend.config.settings import Settings
from backend.geography.models import Region
from backend.shared.db import create_all, make_engine, make_session_factory

ISSUER = "https://jmi.us.auth0.com/"
AUDIENCE = "https://api.job-market-intelligence.test"
JWKS_URL = "https://jmi.us.auth0.com/.well-known/jwks.json"
KID = "test-key-1"
RSA_N_HEX = (
    "a54d17ba4e3fa3a7cae68df2b30280fefca579390e84e4e6c0dc3fbf3e16"
    "26d9d55e5e543b823265bedf6302137e7ff80304316eedc4dd61b560775d4f"
    "32ca23697827d2312b61f742b7b4de77c2e31fec4ab69c612544c9c23650"
    "9e4ca07470a264b393ddac982ab869b1163565ecf1209ed92d3e1ff5664a3"
    "d43e259cb6d6fd06c4fe5096ec273d4c8ac7f43acce1e3040255a300730a"
    "0398af531d10d6b1f51d0e207cfa64474766f05961755c06a17c7097850"
    "8528940e3f901738f9ad127ba98f73bd820e39057272d1b9c14f37911637"
    "0740e83cfab070a1a453723f15fd6942426787996f2fc2c34f0b0491573c"
    "a3a0c196672e56916f558c6386d3b1"
)
RSA_D_HEX = (
    "36c45b9bb10839bf42a4ef9bdd3e73a1c7f0454127b3d52934f5e433072d"
    "8cb2b8945b197a5bf139afab50a0e3f7920b88684fbe8a8da2b19847fd54"
    "4f84aadf5fb6dd2eb176c7af060e5aa128b9cbc98c5ed6b0ea28d0692e"
    "6d1379d736844dbb28352d4511459b45dd52bc6275c232c3d58d6c057cce"
    "301561c6078d2baeb687b8aaac03827f32747211d6af2028d37f773d13f"
    "86a508a9bfad66b536b80fc5c9639724c1493303f2fea01f63da130bbea"
    "238f962fb0d0c57fb871766995f72fc16b0ba8a30325c6b49537b4fa8c"
    "226272200b30327a01a4607db2dd0a59e8eefa8f9b8758fdec5c4df3301a"
    "bfca3db9d9dc5994438bade6eee2f363f56e57"
)
RSA_N = int(RSA_N_HEX, 16)
RSA_D = int(RSA_D_HEX, 16)
RSA_E = 65537


class _JWKSResponse:
    def __enter__(self) -> _JWKSResponse:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(_jwks()).encode("utf-8")


def _client(*, configured: bool = True) -> TestClient:
    engine = make_engine("sqlite:///:memory:")
    create_all(engine)
    settings = Settings(
        app_env="dev",
        database_url="sqlite:///:memory:",
        auth0_issuer=ISSUER if configured else "",
        auth0_audience=AUDIENCE if configured else "",
        auth0_jwks_url=JWKS_URL if configured else "",
        rate_limit_enabled=False,
        security_headers_enabled=False,
        _env_file=None,
    )
    app = create_app(engine=engine, settings=settings)
    app.state._test_engine = engine
    return TestClient(app)


def _seed_region(client: TestClient) -> None:
    factory = make_session_factory(client.app.state.engine)
    session = factory()
    try:
        session.add(
            Region(
                region_id="greater_boston",
                region_name="greater_boston",
                display_name="Greater Boston",
                region_type="greater_region",
            )
        )
        session.commit()
    finally:
        session.close()


def _patch_jwks(monkeypatch) -> None:
    def fake_urlopen(request, timeout: int = 5):  # noqa: ANN001
        assert request.full_url == JWKS_URL
        assert timeout == 5
        return _JWKSResponse()

    monkeypatch.setattr("backend.auth.jwks.urlopen", fake_urlopen)


def _jwks() -> dict[str, Any]:
    return {
        "keys": [
            {
                "kty": "RSA",
                "kid": KID,
                "use": "sig",
                "alg": "RS256",
                "n": _b64url_uint(RSA_N),
                "e": _b64url_uint(RSA_E),
            }
        ]
    }


def _token(
    *,
    issuer: str = ISSUER,
    audience: str | list[str] = AUDIENCE,
    expires_delta: timedelta = timedelta(minutes=5),
    header_overrides: dict[str, Any] | None = None,
    payload_overrides: dict[str, Any] | None = None,
) -> str:
    now = datetime.now(UTC)
    header = {"alg": "RS256", "typ": "JWT", "kid": KID}
    payload = {
        "iss": issuer,
        "sub": "auth0|middleware_user",
        "aud": audience,
        "exp": int((now + expires_delta).timestamp()),
        "iat": int(now.timestamp()),
        "email": "middleware_user@example.com",
        "email_verified": True,
        "name": "Middleware User",
    }
    if header_overrides:
        header.update(header_overrides)
    if payload_overrides:
        payload.update(payload_overrides)
    header_segment = _b64url_json(header)
    payload_segment = _b64url_json(payload)
    signing_input = f"{header_segment}.{payload_segment}".encode("ascii")
    signature = _sign_rs256(signing_input)
    return f"{header_segment}.{payload_segment}.{_b64url(signature)}"


def _unsigned_token() -> str:
    header = _b64url_json({"alg": "none", "typ": "JWT", "kid": KID})
    payload = _b64url_json(
        {
            "iss": ISSUER,
            "sub": "auth0|unsigned",
            "aud": AUDIENCE,
            "exp": int((datetime.now(UTC) + timedelta(minutes=5)).timestamp()),
        }
    )
    return f"{header}.{payload}.unsigned"


def _sign_rs256(signing_input: bytes) -> bytes:
    digest = sha256(signing_input).digest()
    digest_info = SHA256_DIGEST_INFO_PREFIX + digest
    modulus_bytes = (RSA_N.bit_length() + 7) // 8
    padding = b"\xff" * (modulus_bytes - len(digest_info) - 3)
    encoded = b"\x00\x01" + padding + b"\x00" + digest_info
    signature_int = pow(int.from_bytes(encoded, "big"), RSA_D, RSA_N)
    return signature_int.to_bytes(modulus_bytes, "big")


def _b64url_json(value: dict[str, Any]) -> str:
    return _b64url(json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8"))


def _b64url_uint(value: int) -> str:
    return _b64url(value.to_bytes((value.bit_length() + 7) // 8, "big"))


def _b64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def test_valid_mocked_auth0_jwks_token_reaches_me(monkeypatch) -> None:
    _patch_jwks(monkeypatch)
    client = _client()

    response = client.get("/me", headers={"Authorization": f"Bearer {_token()}"})

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["user"]["user_id"].startswith("user_")
    assert body["data"]["profile"]["email"] == "middleware_user@example.com"


def test_missing_token_is_rejected_for_protected_route() -> None:
    response = _client().get("/me")

    assert response.status_code == 401


def test_invalid_signature_is_rejected(monkeypatch) -> None:
    _patch_jwks(monkeypatch)
    token = _token()
    header, payload, signature = token.split(".")
    replacement = "A" if signature[0] != "A" else "B"
    tampered = f"{header}.{payload}.{replacement}{signature[1:]}"

    response = _client().get("/me", headers={"Authorization": f"Bearer {tampered}"})

    assert response.status_code == 401


def test_wrong_issuer_is_rejected(monkeypatch) -> None:
    _patch_jwks(monkeypatch)

    response = _client().get(
        "/me",
        headers={"Authorization": f"Bearer {_token(issuer='https://other.example.com/')}"},
    )

    assert response.status_code == 401


def test_wrong_audience_is_rejected(monkeypatch) -> None:
    _patch_jwks(monkeypatch)

    response = _client().get(
        "/me",
        headers={"Authorization": f"Bearer {_token(audience='https://wrong.example.com')}"},
    )

    assert response.status_code == 401


def test_expired_token_is_rejected(monkeypatch) -> None:
    _patch_jwks(monkeypatch)

    response = _client().get(
        "/me",
        headers={"Authorization": f"Bearer {_token(expires_delta=timedelta(minutes=-5))}"},
    )

    assert response.status_code == 401


def test_unsigned_token_is_rejected(monkeypatch) -> None:
    _patch_jwks(monkeypatch)

    response = _client().get(
        "/me",
        headers={"Authorization": f"Bearer {_unsigned_token()}"},
    )

    assert response.status_code == 401


def test_missing_non_local_auth0_config_fails_closed(monkeypatch) -> None:
    _patch_jwks(monkeypatch)

    response = _client(configured=False).get(
        "/me",
        headers={"Authorization": f"Bearer {_token()}"},
    )

    assert response.status_code == 401


def test_verified_claims_header_is_rejected_outside_local_and_test() -> None:
    response = _client().get(
        "/me",
        headers={
            "X-Verified-OIDC-Claims": json.dumps(
                {"iss": ISSUER, "sub": "auth0|header_user"}
            )
        },
    )

    assert response.status_code == 401


def test_public_market_endpoint_still_works_without_auth() -> None:
    client = _client(configured=False)
    _seed_region(client)

    response = client.get("/regions")

    assert response.status_code == 200
    assert response.json()["data"]["regions"][0]["region_id"] == "greater_boston"
