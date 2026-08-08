# app/routers/__init__.py
"""
API Routers - Modular endpoint organization.

Note: File endpoints are defined in main.py to maintain proper path ordering.
"""

from .admin import router as admin_router
from .ai_manager import router as ai_manager_router
from .audit import router as audit_router
from .auth import router as auth_router
from .command_center import router as command_center_router
from .examples import router as examples_router
from .health import router as health_router
from .items import router as items_router
from .slack_insights import router as slack_insights_router

__all__ = [
    "health_router",
    "ai_manager_router",
    "auth_router",
    "command_center_router",
    "admin_router",
    "audit_router",
    "items_router",
    "slack_insights_router",
    "examples_router",
]
