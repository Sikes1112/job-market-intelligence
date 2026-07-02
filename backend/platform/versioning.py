"""Version and deprecation governance for the Layer 20 Platform API."""

from __future__ import annotations

from dataclasses import dataclass

from backend.platform.public_api_payloads import (
    PLATFORM_PUBLIC_API_SCHEMA_VERSION,
    PLATFORM_PUBLIC_API_VERSION,
)

CURRENT_PLATFORM_API_VERSION = PLATFORM_PUBLIC_API_VERSION
CURRENT_PLATFORM_API_SCHEMA_VERSION = PLATFORM_PUBLIC_API_SCHEMA_VERSION
SUPPORTED_PLATFORM_API_VERSIONS = ("v1",)
MINIMUM_DEPRECATION_NOTICE_DAYS = 180


@dataclass(frozen=True, slots=True)
class PlatformApiDeprecationPolicy:
    minimum_notice_days: int
    additive_changes_without_version_bump: tuple[str, ...]
    breaking_changes_require_new_version: tuple[str, ...]
    sunset_policy: str


PLATFORM_API_DEPRECATION_POLICY = PlatformApiDeprecationPolicy(
    minimum_notice_days=MINIMUM_DEPRECATION_NOTICE_DAYS,
    additive_changes_without_version_bump=(
        "new optional response fields that preserve existing DTO contracts",
        "new products or endpoints under a versioned path",
        "new warning codes with documented semantics",
        "higher tier limits or broader entitlements",
    ),
    breaking_changes_require_new_version=(
        "removing or renaming response fields",
        "changing enum values or field types",
        "changing authentication semantics",
        "tightening existing successful response validation",
        "removing supported products or routes",
    ),
    sunset_policy=(
        "Supported versions receive at least 180 days notice before removal. "
        "Security fixes and leakage protections may ship immediately while "
        "preserving the public-safe envelope shape."
    ),
)


def platform_api_version_document() -> dict:
    return {
        "current_api_version": CURRENT_PLATFORM_API_VERSION,
        "current_schema_version": CURRENT_PLATFORM_API_SCHEMA_VERSION,
        "supported_versions": list(SUPPORTED_PLATFORM_API_VERSIONS),
        "deprecation_policy": {
            "minimum_notice_days": PLATFORM_API_DEPRECATION_POLICY.minimum_notice_days,
            "additive_changes_without_version_bump": list(
                PLATFORM_API_DEPRECATION_POLICY.additive_changes_without_version_bump
            ),
            "breaking_changes_require_new_version": list(
                PLATFORM_API_DEPRECATION_POLICY.breaking_changes_require_new_version
            ),
            "sunset_policy": PLATFORM_API_DEPRECATION_POLICY.sunset_policy,
        },
    }
