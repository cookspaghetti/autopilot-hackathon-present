# app/schemas/__init__.py
from .admin import (
    AdminCreateUser,
    AdminEventResponse,
    ApprovedDomainsRequest,
    ApprovedDomainsResponse,
    BulkActionResponse,
    GroupActionResponse,
    GroupCreateRequest,
    GroupMemberRequest,
    GroupResponse,
    GroupRoleRequest,
    GroupUpdateRequest,
    LoginEventResponse,
    LoginEventsSummaryResponse,
    PaginatedUsersResponse,
    PasswordResetRequest,
    PasswordResetResponse,
    RoleActionResponse,
    RoleCreateRequest,
    RoleResponse,
    RoleUpdateRequest,
    SessionActionResponse,
    SessionResponse,
    SessionStatsResponse,
    UserApprovalResponse,
    UserResponse,
    UserRoleAssignRequest,
    UserRoleResponse,
)
from .audit import AuditLogListResponse, AuditLogResponse, AuditStatsResponse
from .auth import PendingStatusResponse, UserRegistration, UserRegistrationResponse
from .item import Item, ItemBase, ItemCreate

__all__ = [
    # Item schemas
    "ItemBase",
    "ItemCreate",
    "Item",
    # Auth schemas
    "UserRegistration",
    "UserRegistrationResponse",
    "PendingStatusResponse",
    # Admin schemas
    "UserResponse",
    "PaginatedUsersResponse",
    "UserApprovalResponse",
    "AdminCreateUser",
    "BulkActionResponse",
    "ApprovedDomainsRequest",
    "ApprovedDomainsResponse",
    # Role schemas
    "RoleResponse",
    "RoleCreateRequest",
    "RoleUpdateRequest",
    "RoleActionResponse",
    # User role assignment schemas
    "UserRoleAssignRequest",
    "UserRoleResponse",
    # Password reset schemas
    "PasswordResetRequest",
    "PasswordResetResponse",
    # Group schemas
    "GroupResponse",
    "GroupCreateRequest",
    "GroupUpdateRequest",
    "GroupActionResponse",
    "GroupMemberRequest",
    "GroupRoleRequest",
    # Session schemas
    "SessionResponse",
    "SessionStatsResponse",
    "SessionActionResponse",
    # Login events schemas
    "LoginEventResponse",
    "AdminEventResponse",
    "LoginEventsSummaryResponse",
    # Audit schemas
    "AuditLogResponse",
    "AuditLogListResponse",
    "AuditStatsResponse",
]
