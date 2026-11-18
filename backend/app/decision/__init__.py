"""
TrunkHQ — Decision Service Factory.
"""

from app.core.config import get_settings
from app.decision.base import BaseDecisionService
from app.decision.jev_decision import JEVDecisionService
from app.decision.simple_decision import SimpleDecisionService

__all__ = [
    "BaseDecisionService",
    "JEVDecisionService",
    "SimpleDecisionService",
    "get_decision_service",
]


def get_decision_service() -> BaseDecisionService:
    """Return decision service based on configuration."""
    settings = get_settings()
    if settings.jev_enabled:
        return JEVDecisionService()
    return SimpleDecisionService()
