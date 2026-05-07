"""Time-window vocabulary for hiring snapshots.

Per ``STAGE_BY_STAGE_EXECUTION_PROTOCOL.md`` §9, hiring is measured across the
``now``, ``30d``, and ``90d`` core windows. Annualized trend and seasonal
student-hiring signals are contextual layers and live as separate fields on
the hiring snapshot rather than as additional windows.

This module is metadata only — no aggregation, no formula, no scoring.
"""

from __future__ import annotations

from enum import StrEnum


class TimeWindow(StrEnum):
    NOW = "now"
    THIRTY_DAY = "30d"
    NINETY_DAY = "90d"

    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)
