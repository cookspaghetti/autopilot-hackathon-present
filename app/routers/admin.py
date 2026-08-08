# app/routers/admin.py
"""
Admin user management and settings endpoints.
"""

import logging
import os
import secrets
import string

from fastapi import APIRouter, Depends, HTTPException, Request

from ..core.database import get_db
from ..schemas import (
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
    UserRegistrationResponse,
    UserResponse,
    UserRoleAssignRequest,
    UserRoleResponse,
)
from ..security import get_current_user
from ..services.audit import audit

log = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["Admin"])

AUTH_BYPASS = os.getenv("AUTH_BYPASS", "false").lower() == "true"


def _get_keycloak_admin():
    """
    Lazy-load keycloak_admin. When AUTH_BYPASS=true, this is not used.
    Raises 501 if Keycloak admin service is not available.
    """
    try:
        from ..services.keycloak_admin import keycloak_admin

        return keycloak_admin
    except ImportError:
        raise HTTPException(
            status_code=501,
            detail="User management requires Keycloak. Set AUTH_BYPASS=false and configure Keycloak, or re-add keycloak_admin service.",
        )


# Alias for backward compatibility within this file
# All call sites use `keycloak_admin.xxx()` — we make it lazy:
class _LazyKeycloakAdmin:
    """Proxy that defers to the real keycloak_admin on attribute access."""

    def __getattr__(self, name):
        return getattr(_get_keycloak_admin(), name)


keycloak_admin = _LazyKeycloakAdmin()


# =============================================================================
# Password Utilities
# =============================================================================


def generate_strong_password(length: int = 16) -> str:
    """
    Generate a cryptographically secure password that meets strong requirements:
    - At least 16 characters (configurable)
    - At least 1 uppercase letter
    - At least 1 lowercase letter
    - At least 1 digit
    - At least 1 special character
    """
    if length < 12:
        length = 12  # Minimum safe length

    # Character sets
    uppercase = string.ascii_uppercase
    lowercase = string.ascii_lowercase
    digits = string.digits
    special = "!@#$%^&*()_+-=[]{}|;:,.<>?"

    # Ensure at least one of each required type
    password_chars = [
        secrets.choice(uppercase),
        secrets.choice(lowercase),
        secrets.choice(digits),
        secrets.choice(special),
    ]

    # Fill the rest with a mix of all characters
    all_chars = uppercase + lowercase + digits + special
    for _ in range(length - 4):
        password_chars.append(secrets.choice(all_chars))

    # Shuffle to avoid predictable pattern
    secrets.SystemRandom().shuffle(password_chars)

    return "".join(password_chars)


def validate_password_strength(password: str) -> tuple[bool, str]:
    """
    Validate that a password meets minimum strength requirements.
    Returns (is_valid, error_message).
    """
    if len(password) < 12:
        return False, "Password must be at least 12 characters long"

    if not any(c.isupper() for c in password):
        return False, "Password must contain at least one uppercase letter"

    if not any(c.islower() for c in password):
        return False, "Password must contain at least one lowercase letter"

    if not any(c.isdigit() for c in password):
        return False, "Password must contain at least one digit"

    special_chars = set("!@#$%^&*()_+-=[]{}|;:,.<>?")
    if not any(c in special_chars for c in password):
        return (
            False,
            "Password must contain at least one special character (!@#$%^&*()_+-=[]{}|;:,.<>?)",
        )

    return True, ""


# =============================================================================
# USER LISTING
# =============================================================================


@router.get("/users", response_model=PaginatedUsersResponse)
async def list_all_users(
    search: str = "",
    first: int = 0,
    max: int = 50,
    user: dict = Depends(get_current_user),
):
    """
    List users with their roles and status.
    Supports server-side search and pagination.
    Requires 'admin' role.
    """
    try:
        # Clamp page size
        max = min(max, 100)

        # Get total count (matching search filter)
        total = await keycloak_admin.get_users_count(search=search)

        # Get paginated users with roles
        users = await keycloak_admin.get_users_with_roles(
            first=first, max_results=max, search=search
        )

        return PaginatedUsersResponse(
            users=[
                UserResponse(
                    id=u["id"],
                    email=u.get("email", ""),
                    firstName=u.get("firstName"),
                    lastName=u.get("lastName"),
                    enabled=u.get("enabled", True),
                    emailVerified=u.get("emailVerified", False),
                    createdTimestamp=u.get("createdTimestamp"),
                    roles=u.get("roles", []),
                    status=u.get("status", "unknown"),
                )
                for u in users
            ],
            total=total,
            first=first,
            max=max,
        )
    except Exception as e:
        log.error(f"Failed to list users: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/users/pending", response_model=list[UserResponse])
async def list_pending_users(user: dict = Depends(get_current_user)):
    """
    List users pending approval.
    Iterates through all users to find pending ones.
    Requires 'admin' role.
    """
    try:
        users = await keycloak_admin.get_all_users_with_roles_iter()
        pending_users = [u for u in users if u.get("status") == "pending"]
        return [
            UserResponse(
                id=u["id"],
                email=u.get("email", ""),
                firstName=u.get("firstName"),
                lastName=u.get("lastName"),
                enabled=u.get("enabled", True),
                emailVerified=u.get("emailVerified", False),
                createdTimestamp=u.get("createdTimestamp"),
                roles=u.get("roles", []),
                status=u.get("status", "pending"),
            )
            for u in pending_users
        ]
    except Exception as e:
        log.error(f"Failed to list pending users: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# USER CREATION
# =============================================================================


@router.post("/users", response_model=UserRegistrationResponse)
async def admin_create_user(
    user_data: AdminCreateUser,
    user: dict = Depends(get_current_user),
):
    """
    Create a new user with specified role.

    - If password is not provided, a secure one is auto-generated.
    - If temporaryPassword is true (default), user must change password on first login.
    - The password is returned in the response so admin can share it with the user.

    Requires 'admin' role.
    """
    try:
        # Auto-generate password if not provided
        password = user_data.password
        was_auto_generated = False
        if not password:
            password = generate_strong_password(16)
            was_auto_generated = True
            log.info(f"Auto-generated strong password for new user {user_data.email}")
        else:
            # Validate provided password meets strength requirements
            is_valid, error_msg = validate_password_strength(password)
            if not is_valid:
                raise HTTPException(status_code=400, detail=error_msg)

        # Create user in Keycloak
        result = await keycloak_admin.create_user_by_admin(
            email=user_data.email,
            password=password,
            first_name=user_data.firstName,
            last_name=user_data.lastName,
            temporary_password=user_data.temporaryPassword,
        )

        # Assign the specified role
        user_id = result["user_id"]
        actor_email = user.get("email", "unknown")

        if user_data.role == "admin":
            try:
                await keycloak_admin.remove_role(user_id, "pending")
            except Exception:
                pass
            try:
                await keycloak_admin.remove_role(user_id, "user")
            except Exception:
                pass
            await keycloak_admin.assign_role(user_id, "admin")
            result["role"] = "admin"
            result["requires_approval"] = False
            log.info(
                f"[AUDIT] Admin {actor_email} created admin user {user_data.email}"
            )
        elif user_data.role == "user":
            try:
                await keycloak_admin.remove_role(user_id, "pending")
            except Exception:
                pass
            await keycloak_admin.assign_role(user_id, "user")
            result["role"] = "user"
            result["requires_approval"] = False
            log.info(f"[AUDIT] Admin {actor_email} created user {user_data.email}")
        else:  # pending
            try:
                await keycloak_admin.remove_role(user_id, "user")
            except Exception:
                pass
            await keycloak_admin.assign_role(user_id, "pending")
            result["role"] = "pending"
            result["requires_approval"] = True
            log.info(
                f"[AUDIT] Admin {actor_email} created pending user {user_data.email}"
            )

        # Build response message
        temp_note = (
            " (must change on first login)" if user_data.temporaryPassword else ""
        )
        message = f"User created with role '{result['role']}'. Share the password with them securely{temp_note}."

        return UserRegistrationResponse(
            user_id=result["user_id"],
            email=result["email"],
            role=result["role"],
            requires_approval=result["requires_approval"],
            message=message,
            temporary_password=password,  # Return so admin can share it
        )
    except Exception as e:
        log.error(f"Admin create user failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# =============================================================================
# BULK OPERATIONS
# =============================================================================


@router.delete("/users/bulk", response_model=BulkActionResponse)
async def bulk_delete_users_by_domain(
    domain: str,
    request: Request,
    confirm: bool = False,
    user: dict = Depends(get_current_user),
):
    """
    Delete all users from a specific email domain.
    Requires confirm=true and 'admin' role.
    Cannot delete yourself or other admins.
    """
    if not confirm:
        raise HTTPException(
            status_code=400, detail="Must pass confirm=true to execute bulk delete"
        )

    try:
        current_user_id = user.get("sub")
        all_users = await keycloak_admin.get_all_users_with_roles_iter()

        users_to_delete = [
            u
            for u in all_users
            if u.get("email", "").lower().endswith(f"@{domain.lower()}")
            and u.get("id") != current_user_id
            and "admin" not in u.get("roles", [])
        ]

        deleted_count = 0
        deleted_emails = []
        for u in users_to_delete:
            try:
                await keycloak_admin.delete_user(u["id"])
                deleted_count += 1
                deleted_emails.append(u.get("email"))
            except Exception as e:
                log.warning(f"Failed to delete user {u['id']}: {e}")

        await audit.log_bulk_action(
            action="bulk.delete_domain",
            actor=user,
            affected_count=deleted_count,
            description=f"Bulk deleted {deleted_count} users from domain @{domain}",
            metadata={
                "domain": domain,
                "deleted_emails": deleted_emails[:10],
            },  # First 10 for audit
            request=request,
        )
        return BulkActionResponse(
            success=True,
            action="bulk-delete",
            affected_count=deleted_count,
            message=f"Deleted {deleted_count} users from domain @{domain}",
        )
    except Exception as e:
        log.error(f"Bulk delete failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/users/bulk/revoke", response_model=BulkActionResponse)
async def bulk_revoke_users_by_domain(
    domain: str,
    confirm: bool = False,
    user: dict = Depends(get_current_user),
):
    """
    Revoke access for all users from a specific email domain.
    Requires confirm=true and 'admin' role.
    Cannot revoke yourself or other admins.
    """
    if not confirm:
        raise HTTPException(
            status_code=400, detail="Must pass confirm=true to execute bulk revoke"
        )

    try:
        current_user_id = user.get("sub")
        all_users = await keycloak_admin.get_all_users_with_roles_iter()

        users_to_revoke = [
            u
            for u in all_users
            if u.get("email", "").lower().endswith(f"@{domain.lower()}")
            and u.get("id") != current_user_id
            and "admin" not in u.get("roles", [])
            and u.get("enabled", True)
        ]

        actor_email = user.get("email", user.get("preferred_username", "unknown"))
        revoked_count = 0
        for u in users_to_revoke:
            try:
                await keycloak_admin.disable_user(u["id"])
                revoked_count += 1
            except Exception as e:
                log.warning(f"Failed to revoke user {u['id']}: {e}")

        log.info(
            f"[AUDIT] Admin {actor_email} bulk revoked {revoked_count} users from domain @{domain}"
        )
        return BulkActionResponse(
            success=True,
            action="bulk-revoke",
            affected_count=revoked_count,
            message=f"Revoked access for {revoked_count} users from domain @{domain}",
        )
    except Exception as e:
        log.error(f"Bulk revoke failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/users/reset", response_model=BulkActionResponse)
async def reset_all_non_admin_users(
    confirm: bool = False,
    user: dict = Depends(get_current_user),
):
    """
    Delete ALL non-admin users from the realm.
    This is a dangerous operation and requires confirm=true.
    Admins are preserved.
    Requires 'admin' role.
    """
    if not confirm:
        raise HTTPException(
            status_code=400, detail="Must pass confirm=true to execute reset"
        )

    try:
        current_user_id = user.get("sub")
        all_users = await keycloak_admin.get_all_users_with_roles_iter()

        users_to_delete = [
            u
            for u in all_users
            if u.get("id") != current_user_id and "admin" not in u.get("roles", [])
        ]

        actor_email = user.get("email", user.get("preferred_username", "unknown"))
        deleted_count = 0
        for u in users_to_delete:
            try:
                await keycloak_admin.delete_user(u["id"])
                deleted_count += 1
            except Exception as e:
                log.warning(f"Failed to delete user {u['id']}: {e}")

        log.info(
            f"[AUDIT] Admin {actor_email} RESET ALL USERS - deleted {deleted_count} non-admin users"
        )
        return BulkActionResponse(
            success=True,
            action="reset",
            affected_count=deleted_count,
            message=f"Deleted {deleted_count} non-admin users. Admins preserved.",
        )
    except Exception as e:
        log.error(f"Reset all users failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# INDIVIDUAL USER ACTIONS
# =============================================================================


@router.post("/users/{user_id}/approve", response_model=UserApprovalResponse)
async def approve_user(
    user_id: str,
    request: Request,
    user: dict = Depends(get_current_user),
):
    """
    Approve a pending user by changing their role from 'pending' to 'user'.
    Requires 'admin' role.
    """
    try:
        await keycloak_admin.approve_user(user_id)
        await audit.log_user_action(
            action="user.approve",
            actor=user,
            target_user_id=user_id,
            request=request,
        )
        return UserApprovalResponse(
            success=True,
            user_id=user_id,
            action="approved",
            message="User has been approved and now has full access.",
        )
    except Exception as e:
        await audit.log_user_action(
            action="user.approve",
            actor=user,
            target_user_id=user_id,
            success=False,
            error_message=str(e),
            request=request,
        )
        log.error(f"Failed to approve user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/users/{user_id}/reject", response_model=UserApprovalResponse)
async def reject_user(
    user_id: str,
    request: Request,
    disable_only: bool = True,
    user: dict = Depends(get_current_user),
):
    """
    Reject a pending user. By default, disables their account.
    Set disable_only=false to permanently delete the user.
    Requires 'admin' role.
    """
    try:
        await keycloak_admin.reject_user(user_id, disable=disable_only)
        action = "disabled" if disable_only else "deleted"
        await audit.log_user_action(
            action="user.reject",
            actor=user,
            target_user_id=user_id,
            description=f"User rejected ({action})",
            metadata={"disable_only": disable_only},
            request=request,
        )
        return UserApprovalResponse(
            success=True,
            user_id=user_id,
            action=action,
            message=f"User has been {action}.",
        )
    except Exception as e:
        await audit.log_user_action(
            action="user.reject",
            actor=user,
            target_user_id=user_id,
            success=False,
            error_message=str(e),
            request=request,
        )
        log.error(f"Failed to reject user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/users/{user_id}/revoke", response_model=UserApprovalResponse)
async def revoke_user_access(
    user_id: str,
    request: Request,
    user: dict = Depends(get_current_user),
):
    """
    Revoke access for a user by disabling their account.
    The user's data is preserved but they cannot log in.
    Requires 'admin' role.
    """
    try:
        current_user_id = user.get("sub")
        if current_user_id == user_id:
            raise HTTPException(status_code=400, detail="Cannot revoke your own access")

        await keycloak_admin.disable_user(user_id)
        await audit.log_user_action(
            action="user.revoke",
            actor=user,
            target_user_id=user_id,
            request=request,
        )
        return UserApprovalResponse(
            success=True,
            user_id=user_id,
            action="revoked",
            message="User's access has been revoked.",
        )
    except HTTPException:
        raise
    except Exception as e:
        await audit.log_user_action(
            action="user.revoke",
            actor=user,
            target_user_id=user_id,
            success=False,
            error_message=str(e),
            request=request,
        )
        log.error(f"Failed to revoke user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/users/{user_id}/restore", response_model=UserApprovalResponse)
async def restore_user_access(
    user_id: str,
    request: Request,
    user: dict = Depends(get_current_user),
):
    """
    Restore access for a revoked user by enabling their account.
    Requires 'admin' role.
    """
    try:
        await keycloak_admin.enable_user(user_id)
        await audit.log_user_action(
            action="user.restore",
            actor=user,
            target_user_id=user_id,
            request=request,
        )
        return UserApprovalResponse(
            success=True,
            user_id=user_id,
            action="restored",
            message="User's access has been restored.",
        )
    except Exception as e:
        await audit.log_user_action(
            action="user.restore",
            actor=user,
            target_user_id=user_id,
            success=False,
            error_message=str(e),
            request=request,
        )
        log.error(f"Failed to restore user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/users/{user_id}", response_model=UserApprovalResponse)
async def delete_user(
    user_id: str,
    request: Request,
    user: dict = Depends(get_current_user),
):
    """
    Permanently delete a user from Keycloak.
    This action cannot be undone.
    Requires 'admin' role.
    """
    try:
        current_user_id = user.get("sub")
        if current_user_id == user_id:
            raise HTTPException(
                status_code=400, detail="Cannot delete your own account"
            )

        await keycloak_admin.delete_user(user_id)
        await audit.log_user_action(
            action="user.delete",
            actor=user,
            target_user_id=user_id,
            request=request,
        )
        return UserApprovalResponse(
            success=True,
            user_id=user_id,
            action="deleted",
            message="User has been permanently deleted.",
        )
    except HTTPException:
        raise
    except Exception as e:
        await audit.log_user_action(
            action="user.delete",
            actor=user,
            target_user_id=user_id,
            success=False,
            error_message=str(e),
            request=request,
        )
        log.error(f"Failed to delete user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/users/{user_id}/make-admin", response_model=UserApprovalResponse)
async def make_user_admin(
    user_id: str,
    request: Request,
    user: dict = Depends(get_current_user),
):
    """
    Grant admin role to a user.
    Requires 'admin' role.
    """
    try:
        await keycloak_admin.assign_role(user_id, "admin")
        await audit.log_user_action(
            action="user.make_admin",
            actor=user,
            target_user_id=user_id,
            request=request,
        )
        return UserApprovalResponse(
            success=True,
            user_id=user_id,
            action="made-admin",
            message="User has been granted admin privileges.",
        )
    except Exception as e:
        await audit.log_user_action(
            action="user.make_admin",
            actor=user,
            target_user_id=user_id,
            success=False,
            error_message=str(e),
            request=request,
        )
        log.error(f"Failed to make user {user_id} admin: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/users/{user_id}/remove-admin", response_model=UserApprovalResponse)
async def remove_user_admin(
    user_id: str,
    request: Request,
    user: dict = Depends(get_current_user),
):
    """
    Remove admin role from a user.
    Cannot remove admin from yourself.
    Requires 'admin' role.
    """
    try:
        current_user_id = user.get("sub")
        if current_user_id == user_id:
            raise HTTPException(
                status_code=400, detail="Cannot remove your own admin role"
            )

        await keycloak_admin.remove_role(user_id, "admin")
        await audit.log_user_action(
            action="user.remove_admin",
            actor=user,
            target_user_id=user_id,
            request=request,
        )
        return UserApprovalResponse(
            success=True,
            user_id=user_id,
            action="removed-admin",
            message="Admin privileges have been removed from user.",
        )
    except HTTPException:
        raise
    except Exception as e:
        await audit.log_user_action(
            action="user.remove_admin",
            actor=user,
            target_user_id=user_id,
            success=False,
            error_message=str(e),
            request=request,
        )
        log.error(f"Failed to remove admin from user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# USER ROLE ASSIGNMENT
# =============================================================================


@router.get(
    "/users/{user_id}/roles",
    response_model=list[str],
    tags=["Admin User Roles"],
)
async def get_user_roles(
    user_id: str,
    user: dict = Depends(get_current_user),
):
    """
    Get all roles assigned to a user.
    Requires 'admin' role.
    """
    try:
        # Verify user exists first
        user_data = await keycloak_admin.get_user_by_id(user_id)
        if not user_data:
            raise HTTPException(status_code=404, detail="User not found")

        # Get the actual roles from Keycloak
        roles = await keycloak_admin.get_user_roles(user_id)
        return [r["name"] for r in roles]
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Failed to get roles for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/users/{user_id}/roles",
    response_model=UserRoleResponse,
    tags=["Admin User Roles"],
)
async def assign_role_to_user(
    user_id: str,
    role_data: UserRoleAssignRequest,
    request: Request,
    user: dict = Depends(get_current_user),
):
    """
    Assign a role to a user.
    Requires 'admin' role.
    """
    try:
        # Verify user exists
        user_data = await keycloak_admin.get_user_by_id(user_id)
        if not user_data:
            raise HTTPException(status_code=404, detail="User not found")

        # Verify role exists
        role = await keycloak_admin.get_role_by_name(role_data.role_name)
        if not role:
            raise HTTPException(
                status_code=404, detail=f"Role '{role_data.role_name}' not found"
            )

        # Assign the role
        await keycloak_admin.assign_role(user_id, role_data.role_name)

        await audit.log_user_action(
            action="user.assign_role",
            actor=user,
            target_user_id=user_id,
            metadata={"role": role_data.role_name},
            request=request,
        )

        return UserRoleResponse(
            success=True,
            user_id=user_id,
            role_name=role_data.role_name,
            action="assigned",
            message=f"Role '{role_data.role_name}' assigned to user successfully.",
        )
    except HTTPException:
        raise
    except Exception as e:
        await audit.log_user_action(
            action="user.assign_role",
            actor=user,
            target_user_id=user_id,
            success=False,
            error_message=str(e),
            request=request,
        )
        log.error(f"Failed to assign role to user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete(
    "/users/{user_id}/roles/{role_name}",
    response_model=UserRoleResponse,
    tags=["Admin User Roles"],
)
async def remove_role_from_user(
    user_id: str,
    role_name: str,
    request: Request,
    user: dict = Depends(get_current_user),
):
    """
    Remove a role from a user.
    Requires 'admin' role.
    """
    try:
        # Verify user exists
        user_data = await keycloak_admin.get_user_by_id(user_id)
        if not user_data:
            raise HTTPException(status_code=404, detail="User not found")

        # Verify role exists
        role = await keycloak_admin.get_role_by_name(role_name)
        if not role:
            raise HTTPException(status_code=404, detail=f"Role '{role_name}' not found")

        # Remove the role
        await keycloak_admin.remove_role(user_id, role_name)

        await audit.log_user_action(
            action="user.remove_role",
            actor=user,
            target_user_id=user_id,
            metadata={"role": role_name},
            request=request,
        )

        return UserRoleResponse(
            success=True,
            user_id=user_id,
            role_name=role_name,
            action="removed",
            message=f"Role '{role_name}' removed from user successfully.",
        )
    except HTTPException:
        raise
    except Exception as e:
        await audit.log_user_action(
            action="user.remove_role",
            actor=user,
            target_user_id=user_id,
            success=False,
            error_message=str(e),
            request=request,
        )
        log.error(f"Failed to remove role from user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# ADMIN SETTINGS
# =============================================================================


@router.get(
    "/settings/approved-domains",
    response_model=ApprovedDomainsResponse,
    tags=["Admin Settings"],
)
async def get_approved_domains(
    user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Get the list of approved email domains.
    Users from these domains get instant access.
    Requires 'admin' role.
    """
    from ..models.settings import Settings as SettingsModel

    setting = db.query(SettingsModel).filter_by(key="approved_email_domains").first()
    if setting and setting.value:
        domains = [d.strip() for d in setting.value.split(",") if d.strip()]
    else:
        domains = ["example.com"]

    return ApprovedDomainsResponse(
        domains=domains,
        message=f"{len(domains)} approved domain(s) configured.",
    )


@router.post(
    "/settings/approved-domains",
    response_model=ApprovedDomainsResponse,
    tags=["Admin Settings"],
)
async def update_approved_domains(
    request: ApprovedDomainsRequest,
    http_request: Request,
    user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Update the list of approved email domains.
    Requires 'admin' role.
    """
    from ..models.settings import Settings as SettingsModel

    clean_domains = [d.strip().lower() for d in request.domains if d.strip()]
    domains_str = ",".join(clean_domains)

    setting = db.query(SettingsModel).filter_by(key="approved_email_domains").first()
    old_value = setting.value if setting else None

    if setting:
        setting.value = domains_str
    else:
        setting = SettingsModel(
            key="approved_email_domains",
            value=domains_str,
            description="Comma-separated list of email domains that get instant user access",
        )
        db.add(setting)

    db.commit()

    # Update environment variable so keycloak_admin picks it up
    os.environ["APPROVED_EMAIL_DOMAINS"] = domains_str

    # Audit the settings change
    await audit.log_settings_change(
        actor=user,
        setting_key="approved_email_domains",
        old_value=old_value,
        new_value=domains_str,
        description=f"Updated approved domains to: {clean_domains}",
        request=http_request,
    )

    return ApprovedDomainsResponse(
        domains=clean_domains,
        message=f"Updated to {len(clean_domains)} approved domain(s).",
    )


# =============================================================================
# ROLE MANAGEMENT
# =============================================================================


@router.get("/roles", response_model=list[RoleResponse], tags=["Admin Roles"])
async def list_all_roles(user: dict = Depends(get_current_user)):
    """
    List all realm roles with user counts.
    Requires 'admin' role.
    """
    try:
        roles = await keycloak_admin.get_roles_with_user_counts()
        return [
            RoleResponse(
                id=r.get("id"),
                name=r.get("name", ""),
                description=r.get("description"),
                composite=r.get("composite", False),
                clientRole=r.get("clientRole", False),
                containerId=r.get("containerId"),
                userCount=r.get("userCount", 0),
            )
            for r in roles
        ]
    except Exception as e:
        log.error(f"Failed to list roles: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/roles/{role_name}", response_model=RoleResponse, tags=["Admin Roles"])
async def get_role(role_name: str, user: dict = Depends(get_current_user)):
    """
    Get a specific role by name.
    Requires 'admin' role.
    """
    try:
        role = await keycloak_admin.get_role_by_name(role_name)
        if not role:
            raise HTTPException(status_code=404, detail=f"Role '{role_name}' not found")

        user_count = await keycloak_admin.get_role_users_count(role_name)

        return RoleResponse(
            id=role.get("id"),
            name=role.get("name", ""),
            description=role.get("description"),
            composite=role.get("composite", False),
            clientRole=role.get("clientRole", False),
            containerId=role.get("containerId"),
            userCount=user_count,
        )
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Failed to get role {role_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/roles", response_model=RoleActionResponse, tags=["Admin Roles"])
async def create_role(
    role_data: RoleCreateRequest,
    request: Request,
    user: dict = Depends(get_current_user),
):
    """
    Create a new realm role.
    Requires 'admin' role.
    """
    try:
        await keycloak_admin.create_role(
            name=role_data.name,
            description=role_data.description,
        )

        await audit.log_settings_change(
            actor=user,
            setting_key="keycloak_role",
            old_value=None,
            new_value=role_data.name,
            description=f"Created new role: {role_data.name}",
            request=request,
        )

        return RoleActionResponse(
            success=True,
            role_name=role_data.name,
            action="created",
            message=f"Role '{role_data.name}' has been created.",
        )
    except Exception as e:
        log.error(f"Failed to create role: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.put(
    "/roles/{role_name}", response_model=RoleActionResponse, tags=["Admin Roles"]
)
async def update_role(
    role_name: str,
    role_data: RoleUpdateRequest,
    request: Request,
    user: dict = Depends(get_current_user),
):
    """
    Update a role's description.
    Requires 'admin' role.
    """
    try:
        await keycloak_admin.update_role(
            role_name=role_name,
            description=role_data.description,
        )

        await audit.log_settings_change(
            actor=user,
            setting_key="keycloak_role",
            old_value=role_name,
            new_value=f"{role_name}: {role_data.description}",
            description=f"Updated role description: {role_name}",
            request=request,
        )

        return RoleActionResponse(
            success=True,
            role_name=role_name,
            action="updated",
            message=f"Role '{role_name}' has been updated.",
        )
    except Exception as e:
        log.error(f"Failed to update role {role_name}: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.delete(
    "/roles/{role_name}", response_model=RoleActionResponse, tags=["Admin Roles"]
)
async def delete_role(
    role_name: str,
    request: Request,
    user: dict = Depends(get_current_user),
):
    """
    Delete a role.
    System roles (admin, user, pending) cannot be deleted.
    Requires 'admin' role.
    """
    try:
        await keycloak_admin.delete_role(role_name)

        await audit.log_settings_change(
            actor=user,
            setting_key="keycloak_role",
            old_value=role_name,
            new_value=None,
            description=f"Deleted role: {role_name}",
            request=request,
        )

        return RoleActionResponse(
            success=True,
            role_name=role_name,
            action="deleted",
            message=f"Role '{role_name}' has been deleted.",
        )
    except Exception as e:
        log.error(f"Failed to delete role {role_name}: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/roles/{role_name}/users", response_model=list[UserResponse], tags=["Admin Roles"]
)
async def get_role_users(role_name: str, user: dict = Depends(get_current_user)):
    """
    Get all users who have a specific role.
    Requires 'admin' role.
    """
    try:
        users = await keycloak_admin.get_users_by_role(role_name)
        return [
            UserResponse(
                id=u["id"],
                email=u.get("email", ""),
                firstName=u.get("firstName"),
                lastName=u.get("lastName"),
                enabled=u.get("enabled", True),
                emailVerified=u.get("emailVerified", False),
                createdTimestamp=u.get("createdTimestamp"),
                roles=[role_name],
                status="unknown",
            )
            for u in users
        ]
    except Exception as e:
        log.error(f"Failed to get users for role {role_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# PASSWORD RESET BY ADMIN
# =============================================================================


@router.post(
    "/users/{user_id}/reset-password",
    response_model=PasswordResetResponse,
    tags=["Admin Users"],
)
async def reset_user_password(
    user_id: str,
    password_data: PasswordResetRequest,
    request: Request,
    user: dict = Depends(get_current_user),
):
    """
    Reset a user's password (admin action).
    Requires 'admin' role.
    """
    try:
        # Get user info for audit
        target_user = await keycloak_admin.get_user_by_id(user_id)
        if not target_user:
            raise HTTPException(status_code=404, detail="User not found")

        await keycloak_admin.reset_user_password(
            user_id=user_id,
            new_password=password_data.password,
            temporary=password_data.temporary,
        )

        await audit.log_settings_change(
            actor=user,
            setting_key="user_password_reset",
            old_value=None,
            new_value=target_user.get("email", user_id),
            description=f"Admin reset password for user: {target_user.get('email', user_id)}",
            request=request,
        )

        return PasswordResetResponse(
            success=True,
            user_id=user_id,
            temporary=password_data.temporary,
            message=f"Password has been reset for user. "
            + (
                "User must change password on next login."
                if password_data.temporary
                else ""
            ),
        )
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Failed to reset password for user {user_id}: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# =============================================================================
# GROUPS MANAGEMENT
# =============================================================================


@router.get("/groups", response_model=list[GroupResponse], tags=["Admin Groups"])
async def list_all_groups(user: dict = Depends(get_current_user)):
    """
    List all groups with member counts and roles.
    Requires 'admin' role.
    """
    try:
        groups = await keycloak_admin.get_groups_with_details()
        return [_build_group_response(g) for g in groups]
    except Exception as e:
        log.error(f"Failed to get groups: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _build_group_response(group: dict) -> GroupResponse:
    """Helper to build GroupResponse from Keycloak group data."""
    sub_groups = []
    if "subGroups" in group and group["subGroups"]:
        sub_groups = [_build_group_response(sg) for sg in group["subGroups"]]

    return GroupResponse(
        id=group.get("id", ""),
        name=group.get("name", ""),
        path=group.get("path"),
        subGroups=sub_groups,
        memberCount=group.get("memberCount", 0),
        roles=group.get("roles", []),
    )


@router.get("/groups/{group_id}", response_model=GroupResponse, tags=["Admin Groups"])
async def get_group(group_id: str, user: dict = Depends(get_current_user)):
    """
    Get a specific group by ID.
    Requires 'admin' role.
    """
    try:
        group = await keycloak_admin.get_group_by_id(group_id)
        if not group:
            raise HTTPException(status_code=404, detail="Group not found")

        # Enrich with member count and roles
        try:
            members = await keycloak_admin.get_group_members(group_id)
            group["memberCount"] = len(members)
        except Exception:
            group["memberCount"] = 0

        try:
            roles = await keycloak_admin.get_group_role_mappings(group_id)
            group["roles"] = [r["name"] for r in roles]
        except Exception:
            group["roles"] = []

        return _build_group_response(group)
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Failed to get group {group_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/groups", response_model=GroupActionResponse, tags=["Admin Groups"])
async def create_group(
    group_data: GroupCreateRequest,
    request: Request,
    user: dict = Depends(get_current_user),
):
    """
    Create a new group.
    Requires 'admin' role.
    """
    try:
        result = await keycloak_admin.create_group(
            name=group_data.name,
            parent_id=group_data.parentId,
        )

        await audit.log_settings_change(
            actor=user,
            setting_key="keycloak_group",
            old_value=None,
            new_value=group_data.name,
            description=f"Created new group: {group_data.name}",
            request=request,
        )

        return GroupActionResponse(
            success=True,
            group_id=result["id"],
            action="created",
            message=f"Group '{group_data.name}' has been created.",
        )
    except Exception as e:
        log.error(f"Failed to create group: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.put(
    "/groups/{group_id}", response_model=GroupActionResponse, tags=["Admin Groups"]
)
async def update_group(
    group_id: str,
    group_data: GroupUpdateRequest,
    request: Request,
    user: dict = Depends(get_current_user),
):
    """
    Update a group's name.
    Requires 'admin' role.
    """
    try:
        # Get old group info
        old_group = await keycloak_admin.get_group_by_id(group_id)
        old_name = old_group["name"] if old_group else "unknown"

        await keycloak_admin.update_group(group_id, group_data.name)

        await audit.log_settings_change(
            actor=user,
            setting_key="keycloak_group",
            old_value=old_name,
            new_value=group_data.name,
            description=f"Updated group: {old_name} -> {group_data.name}",
            request=request,
        )

        return GroupActionResponse(
            success=True,
            group_id=group_id,
            action="updated",
            message=f"Group has been renamed to '{group_data.name}'.",
        )
    except Exception as e:
        log.error(f"Failed to update group {group_id}: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.delete(
    "/groups/{group_id}", response_model=GroupActionResponse, tags=["Admin Groups"]
)
async def delete_group(
    group_id: str,
    request: Request,
    user: dict = Depends(get_current_user),
):
    """
    Delete a group.
    Requires 'admin' role.
    """
    try:
        # Get group info for audit
        group = await keycloak_admin.get_group_by_id(group_id)
        group_name = group["name"] if group else group_id

        await keycloak_admin.delete_group(group_id)

        await audit.log_settings_change(
            actor=user,
            setting_key="keycloak_group",
            old_value=group_name,
            new_value=None,
            description=f"Deleted group: {group_name}",
            request=request,
        )

        return GroupActionResponse(
            success=True,
            group_id=group_id,
            action="deleted",
            message=f"Group '{group_name}' has been deleted.",
        )
    except Exception as e:
        log.error(f"Failed to delete group {group_id}: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/groups/{group_id}/members",
    response_model=list[UserResponse],
    tags=["Admin Groups"],
)
async def get_group_members(group_id: str, user: dict = Depends(get_current_user)):
    """
    Get all members of a group.
    Requires 'admin' role.
    """
    try:
        members = await keycloak_admin.get_group_members(group_id)
        return [
            UserResponse(
                id=m["id"],
                email=m.get("email", ""),
                firstName=m.get("firstName"),
                lastName=m.get("lastName"),
                enabled=m.get("enabled", True),
                emailVerified=m.get("emailVerified", False),
                createdTimestamp=m.get("createdTimestamp"),
                roles=[],
                status="unknown",
            )
            for m in members
        ]
    except Exception as e:
        log.error(f"Failed to get group members: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/groups/{group_id}/members",
    response_model=GroupActionResponse,
    tags=["Admin Groups"],
)
async def add_group_member(
    group_id: str,
    member_data: GroupMemberRequest,
    request: Request,
    user: dict = Depends(get_current_user),
):
    """
    Add a user to a group.
    Requires 'admin' role.
    """
    try:
        await keycloak_admin.add_user_to_group(member_data.user_id, group_id)

        # Get user and group info for audit
        target_user = await keycloak_admin.get_user_by_id(member_data.user_id)
        group = await keycloak_admin.get_group_by_id(group_id)

        await audit.log_settings_change(
            actor=user,
            setting_key="group_membership",
            old_value=None,
            new_value=f"{target_user.get('email', member_data.user_id)} -> {group.get('name', group_id)}",
            description=f"Added user to group",
            request=request,
        )

        return GroupActionResponse(
            success=True,
            group_id=group_id,
            action="member_added",
            message="User has been added to the group.",
        )
    except Exception as e:
        log.error(f"Failed to add user to group: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.delete(
    "/groups/{group_id}/members/{member_user_id}",
    response_model=GroupActionResponse,
    tags=["Admin Groups"],
)
async def remove_group_member(
    group_id: str,
    member_user_id: str,
    request: Request,
    user: dict = Depends(get_current_user),
):
    """
    Remove a user from a group.
    Requires 'admin' role.
    """
    try:
        await keycloak_admin.remove_user_from_group(member_user_id, group_id)

        await audit.log_settings_change(
            actor=user,
            setting_key="group_membership",
            old_value=f"user:{member_user_id} in group:{group_id}",
            new_value=None,
            description="Removed user from group",
            request=request,
        )

        return GroupActionResponse(
            success=True,
            group_id=group_id,
            action="member_removed",
            message="User has been removed from the group.",
        )
    except Exception as e:
        log.error(f"Failed to remove user from group: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/groups/{group_id}/roles",
    response_model=GroupActionResponse,
    tags=["Admin Groups"],
)
async def assign_role_to_group(
    group_id: str,
    role_data: GroupRoleRequest,
    request: Request,
    user: dict = Depends(get_current_user),
):
    """
    Assign a realm role to a group (all members inherit).
    Requires 'admin' role.
    """
    try:
        await keycloak_admin.assign_role_to_group(group_id, role_data.role_name)

        group = await keycloak_admin.get_group_by_id(group_id)

        await audit.log_settings_change(
            actor=user,
            setting_key="group_role",
            old_value=None,
            new_value=f"{group.get('name', group_id)} <- {role_data.role_name}",
            description=f"Assigned role '{role_data.role_name}' to group",
            request=request,
        )

        return GroupActionResponse(
            success=True,
            group_id=group_id,
            action="role_assigned",
            message=f"Role '{role_data.role_name}' has been assigned to the group.",
        )
    except Exception as e:
        log.error(f"Failed to assign role to group: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.delete(
    "/groups/{group_id}/roles/{role_name}",
    response_model=GroupActionResponse,
    tags=["Admin Groups"],
)
async def remove_role_from_group(
    group_id: str,
    role_name: str,
    request: Request,
    user: dict = Depends(get_current_user),
):
    """
    Remove a realm role from a group.
    Requires 'admin' role.
    """
    try:
        await keycloak_admin.remove_role_from_group(group_id, role_name)

        await audit.log_settings_change(
            actor=user,
            setting_key="group_role",
            old_value=f"group:{group_id} has role:{role_name}",
            new_value=None,
            description=f"Removed role '{role_name}' from group",
            request=request,
        )

        return GroupActionResponse(
            success=True,
            group_id=group_id,
            action="role_removed",
            message=f"Role '{role_name}' has been removed from the group.",
        )
    except Exception as e:
        log.error(f"Failed to remove role from group: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# =============================================================================
# USER SESSIONS MANAGEMENT
# =============================================================================


@router.get("/sessions", response_model=list[SessionResponse], tags=["Admin Sessions"])
async def list_all_sessions(user: dict = Depends(get_current_user)):
    """
    List all active user sessions.
    Requires 'admin' role.
    """
    try:
        sessions = await keycloak_admin.get_all_sessions()
        return [
            SessionResponse(
                id=s.get("id", ""),
                userId=s.get("userId"),
                userEmail=s.get("userEmail"),
                userName=s.get("userName"),
                ipAddress=s.get("ipAddress"),
                start=s.get("start"),
                lastAccess=s.get("lastAccess"),
                clients=s.get("clients"),
            )
            for s in sessions
        ]
    except Exception as e:
        log.error(f"Failed to get sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/sessions/stats", response_model=SessionStatsResponse, tags=["Admin Sessions"]
)
async def get_session_stats(user: dict = Depends(get_current_user)):
    """
    Get session statistics for the realm.
    Requires 'admin' role.
    """
    try:
        stats = await keycloak_admin.get_session_stats()
        return SessionStatsResponse(
            totalActiveSessions=stats.get("totalActiveSessions", 0),
            clientStats=stats.get("clientStats", []),
        )
    except Exception as e:
        log.error(f"Failed to get session stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/users/{user_id}/sessions",
    response_model=list[SessionResponse],
    tags=["Admin Sessions"],
)
async def get_user_sessions(user_id: str, user: dict = Depends(get_current_user)):
    """
    Get all active sessions for a specific user.
    Requires 'admin' role.
    """
    try:
        sessions = await keycloak_admin.get_user_sessions(user_id)
        return [
            SessionResponse(
                id=s.get("id", ""),
                userId=s.get("userId"),
                ipAddress=s.get("ipAddress"),
                start=s.get("start"),
                lastAccess=s.get("lastAccess"),
                clients=s.get("clients"),
            )
            for s in sessions
        ]
    except Exception as e:
        log.error(f"Failed to get user sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete(
    "/sessions/{session_id}",
    response_model=SessionActionResponse,
    tags=["Admin Sessions"],
)
async def terminate_session(
    session_id: str,
    request: Request,
    user: dict = Depends(get_current_user),
):
    """
    Terminate a specific user session.
    Requires 'admin' role.
    """
    try:
        await keycloak_admin.terminate_user_session(session_id)

        await audit.log_settings_change(
            actor=user,
            setting_key="user_session",
            old_value=session_id,
            new_value=None,
            description=f"Terminated session: {session_id}",
            request=request,
        )

        return SessionActionResponse(
            success=True,
            action="terminated",
            message="Session has been terminated.",
            count=1,
        )
    except Exception as e:
        log.error(f"Failed to terminate session: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/users/{user_id}/logout",
    response_model=SessionActionResponse,
    tags=["Admin Sessions"],
)
async def logout_user(
    user_id: str,
    request: Request,
    user: dict = Depends(get_current_user),
):
    """
    Terminate all sessions for a user (force logout).
    Requires 'admin' role.
    """
    try:
        # Get user info for audit
        target_user = await keycloak_admin.get_user_by_id(user_id)
        if not target_user:
            raise HTTPException(status_code=404, detail="User not found")

        count = await keycloak_admin.terminate_all_user_sessions(user_id)

        await audit.log_settings_change(
            actor=user,
            setting_key="user_session",
            old_value=f"all sessions for {target_user.get('email', user_id)}",
            new_value=None,
            description=f"Force logged out user: {target_user.get('email', user_id)}",
            request=request,
        )

        return SessionActionResponse(
            success=True,
            action="logout",
            message=f"User has been logged out from all sessions.",
            count=count,
        )
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Failed to logout user: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# =============================================================================
# LOGIN EVENTS / SECURITY EVENTS
# =============================================================================


@router.get("/events", response_model=list[LoginEventResponse], tags=["Admin Events"])
async def list_login_events(
    event_type: str = None,
    user_id: str = None,
    ip_address: str = None,
    first: int = 0,
    max_results: int = 100,
    user: dict = Depends(get_current_user),
):
    """
    List login/security events.
    Requires 'admin' role.
    """
    try:
        event_types = [event_type] if event_type else None
        events = await keycloak_admin.get_events(
            event_types=event_types,
            user_id=user_id,
            ip_address=ip_address,
            first=first,
            max_results=max_results,
        )
        return [
            LoginEventResponse(
                time=e.get("time"),
                type=e.get("type"),
                realmId=e.get("realmId"),
                clientId=e.get("clientId"),
                userId=e.get("userId"),
                sessionId=e.get("sessionId"),
                ipAddress=e.get("ipAddress"),
                error=e.get("error"),
                details=e.get("details"),
            )
            for e in events
        ]
    except Exception as e:
        log.error(f"Failed to get events: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/events/types", response_model=list[str], tags=["Admin Events"])
async def get_event_types(user: dict = Depends(get_current_user)):
    """
    Get all available event types.
    Requires 'admin' role.
    """
    return await keycloak_admin.get_event_types()


@router.get(
    "/events/summary",
    response_model=LoginEventsSummaryResponse,
    tags=["Admin Events"],
)
async def get_login_events_summary(
    days: int = 7,
    user: dict = Depends(get_current_user),
):
    """
    Get a summary of login events for the past N days.
    Requires 'admin' role.
    """
    try:
        summary = await keycloak_admin.get_login_events_summary(days=days)
        return LoginEventsSummaryResponse(**summary)
    except Exception as e:
        log.error(f"Failed to get events summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/events/admin",
    response_model=list[AdminEventResponse],
    tags=["Admin Events"],
)
async def list_admin_events(
    operation_type: str = None,
    resource_type: str = None,
    first: int = 0,
    max_results: int = 100,
    user: dict = Depends(get_current_user),
):
    """
    List admin events (configuration changes, user management).
    Requires 'admin' role.
    """
    try:
        operation_types = [operation_type] if operation_type else None
        resource_types = [resource_type] if resource_type else None

        events = await keycloak_admin.get_admin_events(
            operation_types=operation_types,
            resource_types=resource_types,
            first=first,
            max_results=max_results,
        )
        return [
            AdminEventResponse(
                time=e.get("time"),
                realmId=e.get("realmId"),
                operationType=e.get("operationType"),
                resourceType=e.get("resourceType"),
                resourcePath=e.get("resourcePath"),
                representation=e.get("representation"),
                error=e.get("error"),
            )
            for e in events
        ]
    except Exception as e:
        log.error(f"Failed to get admin events: {e}")
        raise HTTPException(status_code=500, detail=str(e))
