# app/services/audit.py
"""
Audit Service - Central audit logging engine.

Provides a simple, reusable interface for recording audit events throughout
the application. All audit events are persisted to the database for
compliance, debugging, and analytics.

Usage:
    from app.services.audit import audit

    # Simple audit
    await audit.log(
        action="user.create",
        actor=current_user,
        description="Created new user",
        resource_type="user",
        resource_id=new_user_id,
    )

    # With request context (auto-captures IP, endpoint, etc.)
    await audit.log_request(
        request=request,
        action="user.delete",
        actor=current_user,
        description="Deleted user account",
        resource_type="user",
        resource_id=user_id,
    )
"""

import logging
from datetime import datetime
from typing import Any, Optional

from fastapi import Request
from sqlalchemy.orm import Session

from ..core.database import SessionLocal
from ..models.audit import AuditCategory, AuditLog, AuditSeverity

log = logging.getLogger(__name__)


class AuditService:
    """
    Central audit logging service.

    Design principles:
    - Fire and forget: Audit logging should never block the main operation
    - Fail silently: Audit failures are logged but don't crash the app
    - Context-rich: Capture as much context as possible automatically
    """

    # Standard action names for consistency
    ACTIONS = {
        # Auth
        "auth.login": "User logged in",
        "auth.logout": "User logged out",
        "auth.register": "User registered",
        "auth.password_change": "Password changed",
        # User management
        "user.create": "User created",
        "user.update": "User updated",
        "user.delete": "User deleted",
        "user.approve": "User approved",
        "user.reject": "User rejected",
        "user.revoke": "User access revoked",
        "user.restore": "User access restored",
        "user.make_admin": "User granted admin role",
        "user.remove_admin": "User admin role removed",
        # Bulk operations
        "bulk.delete_domain": "Bulk delete by domain",
        "bulk.revoke_domain": "Bulk revoke by domain",
        "bulk.reset_users": "Reset all non-admin users",
        # Settings
        "settings.update": "Settings updated",
        "settings.domains_update": "Approved domains updated",
        # Data operations
        "data.create": "Record created",
        "data.update": "Record updated",
        "data.delete": "Record deleted",
        # Security
        "security.access_denied": "Access denied",
        "security.invalid_token": "Invalid token detected",
        "security.rate_limited": "Rate limit exceeded",
    }

    def _get_db(self) -> Session:
        """Get a database session."""
        return SessionLocal()

    def _extract_actor_info(self, actor: Optional[dict]) -> tuple[str, str]:
        """Extract actor ID and email from user dict."""
        if not actor:
            return None, "system"

        actor_id = actor.get("sub") or actor.get("id")
        actor_email = (
            actor.get("email")
            or actor.get("preferred_username")
            or actor.get("username")
            or "unknown"
        )
        return actor_id, actor_email

    def _extract_request_info(self, request: Optional[Request]) -> dict:
        """Extract useful info from FastAPI request."""
        if not request:
            return {}

        # Get client IP (handle proxies)
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            client_ip = forwarded.split(",")[0].strip()
        else:
            client_ip = request.client.host if request.client else None

        return {
            "ip": client_ip,
            "user_agent": request.headers.get("user-agent"),
            "endpoint": str(request.url.path),
            "method": request.method,
        }

    async def log(
        self,
        action: str,
        description: str,
        actor: Optional[dict] = None,
        category: str = AuditCategory.ADMIN,
        severity: str = AuditSeverity.INFO,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        resource_name: Optional[str] = None,
        metadata: Optional[dict] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        request: Optional[Request] = None,
        request_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> Optional[int]:
        """
        Log an audit event to the database.

        Args:
            action: Action identifier (e.g., "user.create", "settings.update")
            description: Human-readable description of what happened
            actor: The user performing the action (dict with sub/email)
            category: Category for filtering (see AuditCategory)
            severity: Severity level (see AuditSeverity)
            resource_type: Type of resource affected (e.g., "user", "item")
            resource_id: ID of the affected resource
            resource_name: Human-readable name of the resource
            metadata: Additional structured data
            success: Whether the action succeeded
            error_message: Error details if failed
            request: FastAPI Request object for context
            request_id: Correlation ID for related events
            session_id: User session ID

        Returns:
            Audit log ID if successful, None if failed
        """
        try:
            actor_id, actor_email = self._extract_actor_info(actor)
            request_info = self._extract_request_info(request)

            db = self._get_db()
            try:
                audit_log = AuditLog(
                    # Who
                    actor_id=actor_id,
                    actor_email=actor_email,
                    actor_ip=request_info.get("ip"),
                    actor_user_agent=request_info.get("user_agent"),
                    # What
                    action=action,
                    category=category if isinstance(category, str) else category.value,
                    severity=severity if isinstance(severity, str) else severity.value,
                    # On What
                    resource_type=resource_type,
                    resource_id=str(resource_id) if resource_id else None,
                    resource_name=resource_name,
                    # Details
                    description=description,
                    extra_data=metadata,
                    # Result
                    success="true" if success else "false",
                    error_message=error_message,
                    # Context
                    request_id=request_id,
                    session_id=session_id,
                    endpoint=request_info.get("endpoint"),
                )

                db.add(audit_log)
                db.commit()
                db.refresh(audit_log)

                # Also log to stdout for immediate visibility
                log_level = logging.WARNING if not success else logging.INFO
                log.log(
                    log_level,
                    f"[AUDIT] {action} by {actor_email}: {description}"
                    + (f" (FAILED: {error_message})" if error_message else ""),
                )

                return audit_log.id

            finally:
                db.close()

        except Exception as e:
            # Never let audit failures break the app
            log.error(f"Failed to write audit log: {e}")
            return None

    async def log_user_action(
        self,
        action: str,
        actor: dict,
        target_user_id: str,
        target_user_email: Optional[str] = None,
        description: Optional[str] = None,
        metadata: Optional[dict] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        request: Optional[Request] = None,
    ) -> Optional[int]:
        """
        Convenience method for logging user management actions.

        Args:
            action: Action name (e.g., "user.approve", "user.delete")
            actor: The admin performing the action
            target_user_id: ID of the user being acted upon
            target_user_email: Email of the target user (for readability)
            description: Custom description (auto-generated if not provided)
            metadata: Additional data to store
            success: Whether the action succeeded
            error_message: Error message if failed
            request: FastAPI request for context
        """
        if not description:
            description = self.ACTIONS.get(action, action)
            if target_user_email:
                description = f"{description}: {target_user_email}"

        return await self.log(
            action=action,
            description=description,
            actor=actor,
            category=AuditCategory.USER_MANAGEMENT,
            resource_type="user",
            resource_id=target_user_id,
            resource_name=target_user_email,
            metadata=metadata,
            success=success,
            error_message=error_message,
            request=request,
        )

    async def log_bulk_action(
        self,
        action: str,
        actor: dict,
        affected_count: int,
        description: str,
        metadata: Optional[dict] = None,
        request: Optional[Request] = None,
    ) -> Optional[int]:
        """
        Convenience method for logging bulk operations.

        Args:
            action: Action name (e.g., "bulk.delete_domain")
            actor: The admin performing the action
            affected_count: Number of records affected
            description: Description of what happened
            metadata: Additional data (e.g., domain, filters used)
            request: FastAPI request for context
        """
        meta = metadata or {}
        meta["affected_count"] = affected_count

        return await self.log(
            action=action,
            description=description,
            actor=actor,
            category=AuditCategory.ADMIN,
            severity=AuditSeverity.WARNING,  # Bulk ops are notable
            metadata=meta,
            request=request,
        )

    async def log_settings_change(
        self,
        actor: dict,
        setting_key: str,
        old_value: Any,
        new_value: Any,
        description: Optional[str] = None,
        request: Optional[Request] = None,
    ) -> Optional[int]:
        """
        Convenience method for logging settings changes.

        Args:
            actor: The admin making the change
            setting_key: The setting being changed
            old_value: Previous value
            new_value: New value
            description: Custom description
            request: FastAPI request for context
        """
        return await self.log(
            action="settings.update",
            description=description or f"Updated setting: {setting_key}",
            actor=actor,
            category=AuditCategory.SETTINGS,
            resource_type="setting",
            resource_id=setting_key,
            metadata={
                "old_value": old_value,
                "new_value": new_value,
            },
            request=request,
        )

    async def log_auth_event(
        self,
        action: str,
        actor: Optional[dict] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        metadata: Optional[dict] = None,
        request: Optional[Request] = None,
    ) -> Optional[int]:
        """
        Convenience method for logging authentication events.

        Args:
            action: Auth action (e.g., "auth.login", "auth.logout")
            actor: The user (may be None for failed logins)
            success: Whether the auth succeeded
            error_message: Error message if failed
            metadata: Additional data
            request: FastAPI request for context
        """
        actor_id, actor_email = self._extract_actor_info(actor)

        return await self.log(
            action=action,
            description=self.ACTIONS.get(action, action),
            actor=actor,
            category=AuditCategory.AUTH,
            severity=AuditSeverity.WARNING if not success else AuditSeverity.INFO,
            resource_type="user",
            resource_id=actor_id,
            resource_name=actor_email,
            metadata=metadata,
            success=success,
            error_message=error_message,
            request=request,
        )

    async def log_security_event(
        self,
        action: str,
        description: str,
        actor: Optional[dict] = None,
        metadata: Optional[dict] = None,
        request: Optional[Request] = None,
    ) -> Optional[int]:
        """
        Convenience method for logging security-related events.

        Args:
            action: Security action (e.g., "security.access_denied")
            description: What happened
            actor: The user involved (if known)
            metadata: Additional data
            request: FastAPI request for context
        """
        return await self.log(
            action=action,
            description=description,
            actor=actor,
            category=AuditCategory.SECURITY,
            severity=AuditSeverity.WARNING,
            metadata=metadata,
            request=request,
        )


# Singleton instance for easy import
audit = AuditService()
