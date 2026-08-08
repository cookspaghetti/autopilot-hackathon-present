# app/schemas/admin.py
"""
Pydantic schemas for admin operations.
"""

from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class UserResponse(BaseModel):
    """Response model for user data."""

    id: str
    email: str
    firstName: Optional[str] = None
    lastName: Optional[str] = None
    enabled: bool
    emailVerified: bool
    createdTimestamp: Optional[int] = None
    roles: list[str] = []
    status: str


class PaginatedUsersResponse(BaseModel):
    """Paginated response for user listings."""

    users: list[UserResponse] = []
    total: int
    first: int
    max: int


class UserApprovalResponse(BaseModel):
    """Response for user approval/rejection actions."""

    success: bool
    user_id: str
    action: str
    message: str


class AdminCreateUser(BaseModel):
    """Request model for admin user creation."""

    email: EmailStr
    firstName: str = Field(..., min_length=1, max_length=100)
    lastName: str = Field(..., min_length=1, max_length=100)
    password: Optional[str] = Field(
        None, min_length=8, description="Password (auto-generated if not provided)"
    )
    role: str = Field(
        default="user", description="Initial role: user, admin, or pending"
    )
    temporaryPassword: bool = Field(
        default=True, description="If true, user must change password on first login"
    )


class BulkActionResponse(BaseModel):
    """Response for bulk user operations."""

    success: bool
    action: str
    affected_count: int
    message: str


class ApprovedDomainsRequest(BaseModel):
    """Request model for updating approved domains."""

    domains: list[str]


class ApprovedDomainsResponse(BaseModel):
    """Response model for approved domains."""

    domains: list[str]
    message: str


# =============================================================================
# ROLE MANAGEMENT SCHEMAS
# =============================================================================


class RoleResponse(BaseModel):
    """Response model for role data."""

    id: Optional[str] = None
    name: str
    description: Optional[str] = None
    composite: bool = False
    clientRole: bool = False
    containerId: Optional[str] = None
    userCount: int = 0


class RoleCreateRequest(BaseModel):
    """Request model for creating a new role."""

    name: str = Field(
        ..., min_length=1, max_length=100, pattern=r"^[a-zA-Z][a-zA-Z0-9_-]*$"
    )
    description: str = Field(default="", max_length=500)


class RoleUpdateRequest(BaseModel):
    """Request model for updating a role."""

    description: str = Field(..., max_length=500)


class RoleActionResponse(BaseModel):
    """Response for role management actions."""

    success: bool
    role_name: str
    action: str
    message: str


# =============================================================================
# USER ROLE ASSIGNMENT SCHEMAS
# =============================================================================


class UserRoleAssignRequest(BaseModel):
    """Request model for assigning a role to a user."""

    role_name: str = Field(..., min_length=1, max_length=100)


class UserRoleResponse(BaseModel):
    """Response for user role assignment actions."""

    success: bool
    user_id: str
    role_name: str
    action: str
    message: str


# =============================================================================
# PASSWORD RESET SCHEMAS
# =============================================================================


class PasswordResetRequest(BaseModel):
    """Request model for admin password reset."""

    password: str = Field(..., min_length=12, max_length=128)
    temporary: bool = Field(
        default=True, description="If true, user must change password on next login"
    )


class PasswordResetResponse(BaseModel):
    """Response for password reset action."""

    success: bool
    user_id: str
    temporary: bool
    message: str


# =============================================================================
# GROUP MANAGEMENT SCHEMAS
# =============================================================================


class GroupResponse(BaseModel):
    """Response model for group data."""

    id: str
    name: str
    path: Optional[str] = None
    subGroups: list["GroupResponse"] = []
    memberCount: int = 0
    roles: list[str] = []


class GroupCreateRequest(BaseModel):
    """Request model for creating a group."""

    name: str = Field(..., min_length=1, max_length=100)
    parentId: Optional[str] = None


class GroupUpdateRequest(BaseModel):
    """Request model for updating a group."""

    name: str = Field(..., min_length=1, max_length=100)


class GroupActionResponse(BaseModel):
    """Response for group management actions."""

    success: bool
    group_id: str
    action: str
    message: str


class GroupMemberRequest(BaseModel):
    """Request for adding/removing group members."""

    user_id: str


class GroupRoleRequest(BaseModel):
    """Request for assigning/removing group roles."""

    role_name: str


# =============================================================================
# USER SESSION SCHEMAS
# =============================================================================


class SessionResponse(BaseModel):
    """Response model for user session data."""

    id: str
    userId: Optional[str] = None
    userEmail: Optional[str] = None
    userName: Optional[str] = None
    ipAddress: Optional[str] = None
    start: Optional[int] = None
    lastAccess: Optional[int] = None
    clients: Optional[dict] = None


class SessionStatsResponse(BaseModel):
    """Response for session statistics."""

    totalActiveSessions: int
    clientStats: list[dict] = []


class SessionActionResponse(BaseModel):
    """Response for session management actions."""

    success: bool
    action: str
    message: str
    count: int = 1


# =============================================================================
# LOGIN EVENTS SCHEMAS
# =============================================================================


class LoginEventResponse(BaseModel):
    """Response model for login event data."""

    time: Optional[int] = None
    type: Optional[str] = None
    realmId: Optional[str] = None
    clientId: Optional[str] = None
    userId: Optional[str] = None
    sessionId: Optional[str] = None
    ipAddress: Optional[str] = None
    error: Optional[str] = None
    details: Optional[dict] = None


class AdminEventResponse(BaseModel):
    """Response model for admin event data."""

    time: Optional[int] = None
    realmId: Optional[str] = None
    operationType: Optional[str] = None
    resourceType: Optional[str] = None
    resourcePath: Optional[str] = None
    representation: Optional[str] = None
    error: Optional[str] = None


class LoginEventsSummaryResponse(BaseModel):
    """Response for login events summary."""

    period_days: int
    successful_logins: int
    failed_logins: int
    unique_users: int
    unique_ips: int
    top_failed_ips: list[dict] = []


# Enable forward references for nested GroupResponse
GroupResponse.model_rebuild()
