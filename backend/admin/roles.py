"""Admin role vocabulary and capability helpers."""

from __future__ import annotations

from enum import StrEnum


class AdminRole(StrEnum):
    """Internal roles allowed to access governed admin surfaces."""

    ADMIN = "admin"
    DATA_REVIEWER = "data_reviewer"
    READ_ONLY_OPERATOR = "read_only_operator"

    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)


ADMIN_MUTATION_ROLES: frozenset[AdminRole] = frozenset({AdminRole.ADMIN})
DATA_REVIEW_ROLES: frozenset[AdminRole] = frozenset(
    {AdminRole.ADMIN, AdminRole.DATA_REVIEWER}
)
ADMIN_READ_ROLES: frozenset[AdminRole] = frozenset(AdminRole)


def parse_admin_role(value: str | AdminRole | None) -> AdminRole | None:
    if isinstance(value, AdminRole):
        return value
    if value is None:
        return None
    try:
        return AdminRole(value)
    except ValueError:
        return None


def can_admin_mutate(role: AdminRole | None) -> bool:
    return role in ADMIN_MUTATION_ROLES


def can_review_data(role: AdminRole | None) -> bool:
    return role in DATA_REVIEW_ROLES


def can_read_admin_data(role: AdminRole | None) -> bool:
    return role in ADMIN_READ_ROLES

