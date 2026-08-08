# app/middleware/audit.py
"""
Audit Middleware - Automatic HTTP request/response logging.

=============================================================================
MIDDLEWARE-BASED AUDIT LOGGING
=============================================================================

This middleware automatically logs ALL HTTP requests passing through the API,
providing comprehensive audit trails without requiring any manual code changes.

WHAT GETS LOGGED:
- Every API request (method, endpoint, query params)
- Request body (with sensitive fields masked)
- Response status code
- Response time
- User info (extracted from JWT token)
- Client IP and user agent

WHAT IS EXCLUDED:
- Health check endpoints (/health, /ready, /api/health, /api/ready)
- Static files and assets
- Internal NextJS routes

SENSITIVE DATA HANDLING:
- Fields named 'password', 'secret', 'token', 'key', 'authorization' are masked
- Request/response bodies are truncated to 10KB to prevent DB bloat
- Nested objects are recursively masked

CONFIGURATION:
- AUDIT_MIDDLEWARE_ENABLED: Set to "false" to disable (default: enabled)
- AUDIT_EXCLUDE_PATHS: Comma-separated paths to exclude
- AUDIT_MAX_BODY_SIZE: Max body size to log in bytes (default: 10240)

USAGE:
    # In main.py
    from app.middleware.audit import AuditMiddleware
    app.add_middleware(AuditMiddleware)

=============================================================================
"""

import json
import logging
import os
import re
import time
import uuid
from typing import Any, Callable, Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from ..core.database import SessionLocal
from ..models.audit import AuditCategory, AuditLog, AuditSeverity

log = logging.getLogger(__name__)


class AuditMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware that automatically logs all HTTP requests.

    Features:
    - Zero configuration required
    - Automatic user detection from JWT
    - Smart path exclusion
    - Sensitive data masking
    - Performance tracking
    """

    # Paths to exclude from audit logging (BASE_PATH is prepended in __init__)
    BASE_EXCLUDED_PATHS = [
        r"/health$",
        r"/ready$",
        r"/api/health$",
        r"/api/ready$",
        r"/_next/",
        r"/static/",
        r"/favicon",
        r"/api/admin/audit",  # Don't log audit requests (would be recursive)
    ]

    # Fields to mask in request/response bodies
    SENSITIVE_FIELDS = [
        "password",
        "secret",
        "token",
        "key",
        "authorization",
        "api_key",
        "apikey",
        "access_token",
        "refresh_token",
        "client_secret",
        "private_key",
        "credential",
    ]

    # Maximum body size to log (10KB default)
    MAX_BODY_SIZE = int(os.getenv("AUDIT_MAX_BODY_SIZE", "10240"))

    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.enabled = os.getenv("AUDIT_MIDDLEWARE_ENABLED", "true").lower() != "false"

        # Get BASE_PATH and build excluded paths with it
        base_path = os.getenv("BASE_PATH", "")
        if base_path and not base_path.startswith("/"):
            base_path = f"/{base_path}"
        if base_path == "/":
            base_path = ""

        # Build excluded paths with BASE_PATH prefix
        self.EXCLUDED_PATHS = []
        for path in self.BASE_EXCLUDED_PATHS:
            # Add pattern with BASE_PATH prefix
            if base_path:
                self.EXCLUDED_PATHS.append(f"^{base_path}{path}")
            # Also add pattern without BASE_PATH (for root access)
            self.EXCLUDED_PATHS.append(f"^{path}")

        # Add custom excluded paths from environment
        custom_excludes = os.getenv("AUDIT_EXCLUDE_PATHS", "")
        if custom_excludes:
            self.EXCLUDED_PATHS.extend(custom_excludes.split(","))

    def _should_log(self, path: str) -> bool:
        """Check if this path should be logged."""
        for pattern in self.EXCLUDED_PATHS:
            if re.match(pattern, path):
                return False
        return True

    def _mask_sensitive_data(self, data: Any, depth: int = 0) -> Any:
        """
        Recursively mask sensitive fields in data.

        Examples:
            {"password": "secret123"} -> {"password": "***MASKED***"}
            {"user": {"api_key": "abc"}} -> {"user": {"api_key": "***MASKED***"}}
        """
        if depth > 10:  # Prevent infinite recursion
            return data

        if isinstance(data, dict):
            masked = {}
            for key, value in data.items():
                if any(sensitive in key.lower() for sensitive in self.SENSITIVE_FIELDS):
                    masked[key] = "***MASKED***"
                else:
                    masked[key] = self._mask_sensitive_data(value, depth + 1)
            return masked
        elif isinstance(data, list):
            return [self._mask_sensitive_data(item, depth + 1) for item in data]
        else:
            return data

    def _truncate_body(self, body: str) -> str:
        """Truncate body to max size."""
        if len(body) > self.MAX_BODY_SIZE:
            return (
                body[: self.MAX_BODY_SIZE] + f"... [TRUNCATED, total {len(body)} bytes]"
            )
        return body

    def _parse_and_mask_body(self, body: bytes) -> Optional[str]:
        """Parse body as JSON, mask sensitive fields, and return as string."""
        if not body:
            return None

        try:
            body_str = body.decode("utf-8")
            # Try to parse as JSON for smart masking
            try:
                data = json.loads(body_str)
                masked = self._mask_sensitive_data(data)
                return self._truncate_body(json.dumps(masked))
            except json.JSONDecodeError:
                # Not JSON, just truncate
                return self._truncate_body(body_str)
        except Exception:
            return "[BINARY DATA]"

    def _extract_user_from_request(
        self, request: Request
    ) -> tuple[Optional[str], Optional[str]]:
        """
        Extract user info from request.

        Tries to get user info from:
        1. Request state (set by auth middleware - checked after response)
        2. Authorization header (decode JWT directly)
        """
        # Try request state first (may be set by auth dependencies)
        if hasattr(request.state, "user"):
            user = request.state.user
            if isinstance(user, dict):
                return user.get("sub"), user.get("email") or user.get(
                    "preferred_username"
                )

        # Decode JWT from Authorization header
        auth_header = request.headers.get("authorization")
        if auth_header and auth_header.lower().startswith("bearer "):
            token = auth_header[7:]  # Remove "Bearer " prefix
            try:
                # Decode JWT without verification (we just need the claims)
                # The actual verification is done by the auth middleware
                import base64

                # JWT has 3 parts: header.payload.signature
                parts = token.split(".")
                if len(parts) >= 2:
                    # Decode payload (add padding if needed)
                    payload = parts[1]
                    padding = 4 - len(payload) % 4
                    if padding != 4:
                        payload += "=" * padding

                    decoded = base64.urlsafe_b64decode(payload)
                    claims = json.loads(decoded)

                    user_id = claims.get("sub")
                    user_email = (
                        claims.get("email")
                        or claims.get("preferred_username")
                        or claims.get("username")
                    )

                    if user_id or user_email:
                        return user_id, user_email
            except Exception as e:
                log.debug(f"[AUDIT] Failed to decode JWT: {e}")

        # For unauthenticated requests
        return None, None

    def _get_client_ip(self, request: Request) -> str:
        """Get client IP, handling proxies."""
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        if request.client:
            return request.client.host
        return "unknown"

    def _categorize_endpoint(self, path: str, method: str) -> tuple[str, str]:
        """
        Auto-detect category and action from endpoint.

        Returns:
            (category, action) tuple
        """
        # Admin endpoints
        if "/admin/" in path:
            if "/users" in path:
                return (
                    AuditCategory.USER_MANAGEMENT,
                    f"api.{method.lower()}.admin.users",
                )
            if "/settings" in path:
                return AuditCategory.SETTINGS, f"api.{method.lower()}.admin.settings"
            if "/audit" in path:
                return AuditCategory.ADMIN, f"api.{method.lower()}.admin.audit"
            return AuditCategory.ADMIN, f"api.{method.lower()}.admin"

        # Auth endpoints
        if "/auth/" in path:
            return AuditCategory.AUTH, f"api.{method.lower()}.auth"

        # Default to API category
        return AuditCategory.API, f"api.{method.lower()}"

    def _severity_from_status(self, status_code: int) -> str:
        """Determine severity from HTTP status code."""
        if status_code >= 500:
            return AuditSeverity.ERROR
        if status_code >= 400:
            return AuditSeverity.WARNING
        return AuditSeverity.INFO

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and log audit entry."""
        # Skip if disabled or excluded path
        if not self.enabled or not self._should_log(request.url.path):
            return await call_next(request)

        # Generate request ID for correlation
        request_id = str(uuid.uuid4())[:8]

        # Start timing
        start_time = time.time()

        # Read request body (need to cache it since it's a stream)
        request_body = None
        if request.method in ["POST", "PUT", "PATCH"]:
            try:
                body = await request.body()
                request_body = self._parse_and_mask_body(body)

                # We need to reset the body since we consumed it
                # FastAPI handles this automatically with the Request object
            except Exception:
                request_body = "[BODY READ ERROR]"

        # Process request
        response = None
        error_message = None
        try:
            response = await call_next(request)
        except Exception as e:
            error_message = str(e)
            raise
        finally:
            # Calculate response time
            response_time_ms = (time.time() - start_time) * 1000

            # Extract user info
            actor_id, actor_email = self._extract_user_from_request(request)

            # Get category and action
            category, action = self._categorize_endpoint(
                request.url.path, request.method
            )

            # Determine status code and severity
            status_code = response.status_code if response else 500
            severity = self._severity_from_status(status_code)
            success = "true" if status_code < 400 else "false"

            # Build description
            description = f"{request.method} {request.url.path}"
            if status_code >= 400:
                description += f" -> {status_code}"

            # Get query params
            query_params = str(request.query_params) if request.query_params else None

            # Log to database asynchronously (fire and forget)
            try:
                self._log_to_db(
                    request_id=request_id,
                    actor_id=actor_id,
                    actor_email=actor_email,
                    actor_ip=self._get_client_ip(request),
                    actor_user_agent=request.headers.get("user-agent"),
                    action=action,
                    category=(
                        category.value
                        if isinstance(category, AuditCategory)
                        else category
                    ),
                    severity=(
                        severity.value
                        if isinstance(severity, AuditSeverity)
                        else severity
                    ),
                    description=description,
                    endpoint=request.url.path,
                    http_method=request.method,
                    request_body=request_body,
                    query_params=query_params,
                    response_status=status_code,
                    response_time_ms=response_time_ms,
                    success=success,
                    error_message=error_message,
                )
            except Exception as e:
                # Never let audit logging break the request
                log.error(f"[AUDIT MIDDLEWARE] Failed to log: {e}")

        return response

    def _log_to_db(
        self,
        request_id: str,
        actor_id: Optional[str],
        actor_email: Optional[str],
        actor_ip: str,
        actor_user_agent: Optional[str],
        action: str,
        category: str,
        severity: str,
        description: str,
        endpoint: str,
        http_method: str,
        request_body: Optional[str],
        query_params: Optional[str],
        response_status: int,
        response_time_ms: float,
        success: str,
        error_message: Optional[str],
    ):
        """Write audit log to database (synchronous for middleware)."""
        db = SessionLocal()
        try:
            audit_log = AuditLog(
                request_id=request_id,
                actor_id=actor_id,
                actor_email=actor_email or "anonymous",
                actor_ip=actor_ip,
                actor_user_agent=actor_user_agent,
                action=action,
                category=category,
                severity=severity,
                description=description,
                endpoint=endpoint,
                http_method=http_method,
                request_body=request_body,
                query_params=query_params,
                response_status=response_status,
                response_time_ms=response_time_ms,
                success=success,
                error_message=error_message,
                is_middleware=True,
            )
            db.add(audit_log)
            db.commit()
        except Exception as e:
            log.error(f"[AUDIT MIDDLEWARE] DB error: {e}")
            db.rollback()
        finally:
            db.close()
