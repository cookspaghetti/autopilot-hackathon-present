# app/schemas/audit.py
"""
Pydantic schemas for audit log operations.

Supports both:
- Middleware-generated logs (automatic HTTP request/response logging)
- Custom logs (manual logging with rich business context)
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class AuditLogResponse(BaseModel):
    """
    Response model for a single audit log entry.

    Includes both custom log fields and middleware-specific fields.
    The `is_middleware` field indicates whether this was auto-logged.
    """

    id: int
    timestamp: datetime

    # Who
    actor_id: Optional[str] = None
    actor_email: Optional[str] = None
    actor_ip: Optional[str] = None
    actor_user_agent: Optional[str] = None

    # What
    action: str
    category: str
    severity: str

    # On What
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    resource_name: Optional[str] = None

    # Details
    description: str
    extra_data: Optional[dict[str, Any]] = None

    # Result
    success: str
    error_message: Optional[str] = None

    # Context
    endpoint: Optional[str] = None
    request_id: Optional[str] = None
    session_id: Optional[str] = None

    # Middleware-specific fields (populated for automatic logs)
    http_method: Optional[str] = None
    request_body: Optional[str] = None
    query_params: Optional[str] = None
    response_status: Optional[int] = None
    response_time_ms: Optional[float] = None
    is_middleware: bool = False

    model_config = ConfigDict(from_attributes=True)


class AuditLogListResponse(BaseModel):
    """Response model for paginated audit logs."""

    logs: list[AuditLogResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class AuditLogFilters(BaseModel):
    """Filters for querying audit logs."""

    category: Optional[str] = None
    action: Optional[str] = None
    actor_email: Optional[str] = None
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    success: Optional[bool] = None
    severity: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    # Middleware-specific filters
    http_method: Optional[str] = None
    response_status: Optional[int] = None
    is_middleware: Optional[bool] = None


class AuditStatsResponse(BaseModel):
    """Response model for audit statistics."""

    total_events: int
    events_today: int
    events_this_week: int
    by_category: dict[str, int]
    by_action: dict[str, int]
    recent_errors: int
    # Middleware-specific stats
    by_http_method: Optional[dict[str, int]] = None
    by_status_code: Optional[dict[str, int]] = None
    avg_response_time_ms: Optional[float] = None
    middleware_logs: int = 0
    custom_logs: int = 0
