"""Geography-domain enums."""

from __future__ import annotations

from enum import StrEnum


class RegionType(StrEnum):
    CITY = "city"
    METRO = "metro"
    GREATER_REGION = "greater_region"
    STATE = "state"
    CUSTOM_REGION = "custom_region"

    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)
