"""Auth0/OIDC JWT verification against a JWKS endpoint.

The verifier is intentionally narrow: Auth0 access tokens for this API are
expected to be RS256-signed JWTs with issuer, audience, expiration, and subject
claims. The code never decodes tokens as trusted data until the RSA signature has
been checked against a cached JWKS key.
"""

from __future__ import annotations

import base64
import binascii
import json
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from hmac import compare_digest
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

SHA256_DIGEST_INFO_PREFIX = bytes.fromhex("3031300d060960864801650304020105000420")
SUPPORTED_ALGORITHM = "RS256"
SUPPORTED_TOKEN_TYPES = frozenset({"jwt", "at+jwt"})
MIN_RSA_MODULUS_BITS = 2048


class Auth0JWTError(ValueError):
    """Raised when a Bearer token cannot be verified as an Auth0 JWT."""


@dataclass(frozen=True, slots=True)
class Auth0JWTConfig:
    issuer: str
    audience: str
    jwks_url: str
    jwks_cache_seconds: int = 300

    @property
    def is_configured(self) -> bool:
        return bool(self.issuer and self.audience and self.jwks_url)


class Auth0JWTVerifier:
    """Verify Auth0 RS256 JWTs and return claims only after verification."""

    def __init__(self, config: Auth0JWTConfig) -> None:
        self._config = config
        self._cached_jwks: dict[str, Any] | None = None
        self._cached_until = 0.0

    def verify(self, token: str) -> dict[str, Any]:
        if not self._config.is_configured:
            raise Auth0JWTError("Auth0 JWT verification is not configured")

        header_segment, payload_segment, signature_segment = _split_jwt(token)
        header = _json_segment(header_segment, "header")
        signing_input = f"{header_segment}.{payload_segment}".encode("ascii")
        signature = _decode_segment(signature_segment, "signature")

        kid = _validate_header(header)
        jwk = self._jwk_for_kid(kid)
        _verify_rs256_signature(jwk, signing_input, signature)
        payload = _json_segment(payload_segment, "payload")
        self._validate_claims(payload)
        return dict(payload)

    def _jwk_for_kid(self, kid: str) -> dict[str, Any]:
        jwks = self._jwks()
        jwk = _find_jwk(jwks, kid)
        if jwk is not None:
            return jwk

        # A missing key may mean Auth0 rotated signing keys. Bypass the cache
        # once before failing closed.
        jwks = self._jwks(force_refresh=True)
        jwk = _find_jwk(jwks, kid)
        if jwk is None:
            raise Auth0JWTError("JWT signing key was not found in JWKS")
        return jwk

    def _jwks(self, *, force_refresh: bool = False) -> dict[str, Any]:
        now = time.monotonic()
        if not force_refresh and self._cached_jwks is not None and now < self._cached_until:
            return self._cached_jwks

        request = Request(
            self._config.jwks_url,
            headers={
                "Accept": "application/json",
                "User-Agent": "job-market-intelligence-auth0-jwks/1.0",
            },
        )
        try:
            with urlopen(request, timeout=5) as response:
                raw = response.read()
        except (OSError, URLError) as exc:
            raise Auth0JWTError("Unable to fetch Auth0 JWKS") from exc

        try:
            jwks = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise Auth0JWTError("Auth0 JWKS response is not valid JSON") from exc

        if not isinstance(jwks, dict) or not isinstance(jwks.get("keys"), list):
            raise Auth0JWTError("Auth0 JWKS response must contain keys")

        self._cached_jwks = dict(jwks)
        self._cached_until = now + max(1, self._config.jwks_cache_seconds)
        return self._cached_jwks

    def _validate_claims(self, payload: dict[str, Any]) -> None:
        issuer = payload.get("iss")
        if issuer != self._config.issuer:
            raise Auth0JWTError("JWT issuer is invalid")

        if not _audience_matches(payload.get("aud"), self._config.audience):
            raise Auth0JWTError("JWT audience is invalid")

        subject = payload.get("sub")
        if not isinstance(subject, str) or not subject.strip():
            raise Auth0JWTError("JWT subject is missing")

        now = datetime.now(UTC).timestamp()
        expires_at = _numeric_date(payload.get("exp"), "exp")
        if expires_at <= now:
            raise Auth0JWTError("JWT has expired")

        not_before = payload.get("nbf")
        if not_before is not None and _numeric_date(not_before, "nbf") > now:
            raise Auth0JWTError("JWT is not valid yet")

        issued_at = payload.get("iat")
        if issued_at is not None and _numeric_date(issued_at, "iat") > now + 60:
            raise Auth0JWTError("JWT issued-at time is in the future")

        token_use = payload.get("token_use")
        if token_use is not None and token_use != "access":
            raise Auth0JWTError("JWT token_use is invalid")


def auth0_config_from_settings(settings: Any) -> Auth0JWTConfig:
    issuer = str(getattr(settings, "auth0_issuer", "") or "").strip()
    audience = str(getattr(settings, "auth0_audience", "") or "").strip()
    jwks_url = str(getattr(settings, "auth0_jwks_url", "") or "").strip()
    cache_seconds = int(getattr(settings, "auth0_jwks_cache_seconds", 300) or 300)
    if issuer and not jwks_url:
        jwks_url = f"{issuer.rstrip('/')}/.well-known/jwks.json"
    return Auth0JWTConfig(
        issuer=issuer,
        audience=audience,
        jwks_url=jwks_url,
        jwks_cache_seconds=cache_seconds,
    )


def _split_jwt(token: str) -> tuple[str, str, str]:
    parts = token.split(".")
    if len(parts) != 3 or not all(parts):
        raise Auth0JWTError("Bearer token must be a compact JWT")
    return parts[0], parts[1], parts[2]


def _json_segment(segment: str, name: str) -> dict[str, Any]:
    try:
        decoded = _decode_segment(segment, name)
        value = json.loads(decoded.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Auth0JWTError(f"JWT {name} is not valid JSON") from exc
    if not isinstance(value, dict):
        raise Auth0JWTError(f"JWT {name} must be an object")
    return value


def _decode_segment(segment: str, name: str) -> bytes:
    if not segment:
        raise Auth0JWTError(f"JWT {name} segment is missing")
    padded = segment + "=" * (-len(segment) % 4)
    try:
        return base64.b64decode(padded.encode("ascii"), altchars=b"-_", validate=True)
    except (binascii.Error, UnicodeEncodeError) as exc:
        raise Auth0JWTError(f"JWT {name} segment is not base64url") from exc


def _validate_header(header: dict[str, Any]) -> str:
    if header.get("alg") != SUPPORTED_ALGORITHM:
        raise Auth0JWTError("JWT algorithm must be RS256")
    token_type = header.get("typ")
    if token_type is not None:
        if not isinstance(token_type, str) or token_type.lower() not in SUPPORTED_TOKEN_TYPES:
            raise Auth0JWTError("JWT type is invalid")
    kid = header.get("kid")
    if not isinstance(kid, str) or not kid.strip():
        raise Auth0JWTError("JWT key id is missing")
    return kid.strip()


def _find_jwk(jwks: dict[str, Any], kid: str) -> dict[str, Any] | None:
    for key in jwks.get("keys", []):
        if isinstance(key, dict) and key.get("kid") == kid:
            return key
    return None


def _verify_rs256_signature(
    jwk: dict[str, Any],
    signing_input: bytes,
    signature: bytes,
) -> None:
    if jwk.get("kty") != "RSA":
        raise Auth0JWTError("JWT signing key must be RSA")
    if jwk.get("alg") not in {None, SUPPORTED_ALGORITHM}:
        raise Auth0JWTError("JWT signing key algorithm is invalid")
    if jwk.get("use") not in {None, "sig"}:
        raise Auth0JWTError("JWT signing key use is invalid")
    key_ops = jwk.get("key_ops")
    if key_ops is not None and (
        not isinstance(key_ops, list) or "verify" not in key_ops
    ):
        raise Auth0JWTError("JWT signing key is not usable for verification")

    modulus = _jwk_int(jwk, "n")
    exponent = _jwk_int(jwk, "e")
    modulus_bytes = (modulus.bit_length() + 7) // 8
    if modulus.bit_length() < MIN_RSA_MODULUS_BITS:
        raise Auth0JWTError("JWT signing key is too small")
    if len(signature) != modulus_bytes:
        raise Auth0JWTError("JWT signature length is invalid")

    signature_int = int.from_bytes(signature, "big")
    encoded = pow(signature_int, exponent, modulus).to_bytes(modulus_bytes, "big")
    expected_digest = sha256(signing_input).digest()
    expected_encoded = _emsa_pkcs1_v1_5_sha256(expected_digest, modulus_bytes)
    if not compare_digest(encoded, expected_encoded):
        raise Auth0JWTError("JWT signature is invalid")


def _jwk_int(jwk: dict[str, Any], name: str) -> int:
    value = jwk.get(name)
    if not isinstance(value, str) or not value:
        raise Auth0JWTError(f"JWK value {name!r} is missing")
    return int.from_bytes(_decode_segment(value, f"jwk_{name}"), "big")


def _emsa_pkcs1_v1_5_sha256(digest: bytes, modulus_bytes: int) -> bytes:
    digest_info = SHA256_DIGEST_INFO_PREFIX + digest
    padding_length = modulus_bytes - len(digest_info) - 3
    if padding_length < 8:
        raise Auth0JWTError("RSA key is too small for RS256")
    return b"\x00\x01" + (b"\xff" * padding_length) + b"\x00" + digest_info


def _audience_matches(audience_claim: Any, expected: str) -> bool:
    if isinstance(audience_claim, str):
        return audience_claim == expected
    if isinstance(audience_claim, list) and all(
        isinstance(item, str) for item in audience_claim
    ):
        return expected in audience_claim
    return False


def _numeric_date(value: Any, claim_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise Auth0JWTError(f"JWT {claim_name} claim must be a numeric date")
    return float(value)
