"""User-facing intelligence dashboard contracts for Layer 30.1."""

from backend.user_intelligence.schemas import UserIntelligenceDashboardResponse
from backend.user_intelligence.service import UserIntelligenceDashboardService

__all__ = [
    "UserIntelligenceDashboardResponse",
    "UserIntelligenceDashboardService",
]
