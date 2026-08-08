# app/models/audit.py
"""
Audit Log Model - Critical event tracking for compliance and debugging.

=============================================================================
AUDIT LOGGING SYSTEM OVERVIEW
=============================================================================

This module provides comprehensive audit logging with TWO complementary modes:

1. MIDDLEWARE LOGGING (Automatic)
   - Captures ALL HTTP requests automatically via AuditMiddleware
   - Records: method, endpoint, status code, response time, request/response bodies
   - No developer intervention needed - every endpoint is logged
   - Best for: Compliance, debugging, API usage analytics

2. CUSTOM LOGGING (Manual)
   - Rich, business-context-aware logging via audit service
   - Records: "Admin approved user john@example.com for role manager"
   - Developer adds calls for important business events
   - Best for: Business auditing, admin action tracking

USAGE EXAMPLES:
---------------
# Automatic (no code needed - middleware handles it)
# Every request to /api/* is automatically logged

# Custom logging for rich context:
from app.services.audit import audit

await audit.log_user_action(
    action="user.approve",
    actor=current_user,
    target_user_id=user_id,
    target_user_email="john@example.com",
)

FILTERING:
----------
- Health checks (/health, /ready) are excluded
- Static files are excluded
- Sensitive fields (password, token, secret) are masked
- Request/response bodies are truncated to 10KB

EXPORT:
-------
- GET /api/admin/audit/export?format=csv
- GET /api/admin/audit/export?format=excel
=============================================================================
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import declarative_base

from ..core.database import Base


class AuditCategory(str, Enum):
    """Categories of audit events for filtering and analysis."""

    AUTH = "auth"  # Login, logout, registration
    USER_MANAGEMENT = "user_management"  # CRUD on users
    ADMIN = "admin"  # Admin-specific actions
    SETTINGS = "settings"  # Configuration changes
    DATA = "data"  # CRUD on business data
    SECURITY = "security"  # Security-related events
    SYSTEM = "system"  # System events (startup, shutdown, etc.)
    API = "api"  # API access patterns (middleware-generated)
    ERROR = "error"  # Error events


class AuditSeverity(str, Enum):
    """Severity levels for audit events."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AuditLog(Base):
    """
    Audit log entry - immutable record of an action.

    Design principles:
    - Immutable: Records are never updated or deleted
    - Comprehensive: Captures all relevant context
    - Queryable: Indexed for fast filtering
    - Flexible: extra_data JSON for custom fields

    This model supports both:
    - Middleware-generated logs (automatic, captures HTTP request/response)
    - Custom logs (manual, with rich business context)
    """

    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)

    # When
    timestamp = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    # Who
    actor_id = Column(
        String(255), nullable=True, index=True
    )  # User ID (null for system/anonymous)
    actor_email = Column(String(255), nullable=True, index=True)  # For easy reading
    actor_ip = Column(String(45), nullable=True)  # IPv4 or IPv6
    actor_user_agent = Column(Text, nullable=True)

    # What
    action = Column(
        String(100), nullable=False, index=True
    )  # e.g., "user.create", "api.request"
    category = Column(String(50), nullable=False, index=True)  # AuditCategory value
    severity = Column(String(20), nullable=False, default="info")  # AuditSeverity value

    # On What (the target of the action)
    resource_type = Column(
        String(100), nullable=True, index=True
    )  # e.g., "user", "item", "setting"
    resource_id = Column(
        String(255), nullable=True, index=True
    )  # ID of the affected resource
    resource_name = Column(String(255), nullable=True)  # Human-readable name

    # Details
    description = Column(Text, nullable=False)  # Human-readable description
    extra_data = Column(JSON, nullable=True)  # Additional structured data

    # Result
    success = Column(
        String(10), nullable=False, default="true"
    )  # "true", "false", "partial"
    error_message = Column(Text, nullable=True)  # Error details if failed

    # Context
    request_id = Column(String(100), nullable=True)  # For correlating related events
    session_id = Column(String(255), nullable=True)  # User session
    endpoint = Column(String(255), nullable=True, index=True)  # API endpoint called

    # =========================================================================
    # MIDDLEWARE-SPECIFIC FIELDS (for automatic HTTP request logging)
    # =========================================================================
    # These fields are populated automatically by AuditMiddleware

    # HTTP Request Details
    http_method = Column(
        String(10), nullable=True, index=True
    )  # GET, POST, PUT, DELETE
    request_body = Column(Text, nullable=True)  # Request body (masked, truncated)
    query_params = Column(Text, nullable=True)  # Query string parameters

    # HTTP Response Details
    response_status = Column(
        Integer, nullable=True, index=True
    )  # HTTP status code (200, 404, 500)
    response_time_ms = Column(Float, nullable=True)  # Response time in milliseconds
    response_body = Column(Text, nullable=True)  # Response body (masked, truncated)

    # Source indicator
    is_middleware = Column(
        Boolean, nullable=False, default=False
    )  # True if auto-logged by middleware

    def __repr__(self):
        return f"<AuditLog {self.id}: {self.action} by {self.actor_email}>"

    def to_export_dict(self) -> dict:
        """Convert to dictionary for CSV/Excel export."""
        return {
            "ID": self.id,
            "Timestamp": self.timestamp.isoformat() if self.timestamp else "",
            "Actor Email": self.actor_email or "",
            "Actor IP": self.actor_ip or "",
            "Action": self.action,
            "Category": self.category,
            "Severity": self.severity,
            "Resource Type": self.resource_type or "",
            "Resource ID": self.resource_id or "",
            "Description": self.description,
            "Success": self.success,
            "Error": self.error_message or "",
            "HTTP Method": self.http_method or "",
            "Endpoint": self.endpoint or "",
            "Status Code": self.response_status or "",
            "Response Time (ms)": (
                round(self.response_time_ms, 2) if self.response_time_ms else ""
            ),
            "Source": "Middleware" if self.is_middleware else "Custom",
        }
