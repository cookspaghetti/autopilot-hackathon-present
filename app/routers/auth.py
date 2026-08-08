# app/routers/auth.py
"""
Authentication and registration endpoints.

When AUTH_BYPASS=true (default in dev), registration returns a mock success response
since there is no Keycloak backend. Disable AUTH_BYPASS and configure Keycloak
for real user registration.
"""

import logging
import os

from fastapi import APIRouter, Depends, HTTPException

from ..schemas import UserRegistration, UserRegistrationResponse
from ..security import get_current_user

log = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Auth"])

AUTH_BYPASS = os.getenv("AUTH_BYPASS", "false").lower() == "true"


@router.post("/register", response_model=UserRegistrationResponse)
async def register_user(registration: UserRegistration):
    """
    Register a new user.

    - When AUTH_BYPASS=true: returns a mock success response (no Keycloak needed).
    - When AUTH_BYPASS=false: requires Keycloak to be configured.
    """
    if AUTH_BYPASS:
        # Dev mode — return mock registration success
        return UserRegistrationResponse(
            user_id=f"dev-{registration.email.split('@')[0]}",
            email=registration.email,
            role="user",
            requires_approval=False,
            message="Registration successful (dev mode — AUTH_BYPASS is enabled).",
        )

    # Production mode — requires keycloak_admin service
    try:
        from ..services.keycloak_admin import keycloak_admin

        result = await keycloak_admin.create_user(
            email=registration.email,
            password=registration.password,
            first_name=registration.first_name,
            last_name=registration.last_name,
            email_verified=False,
        )

        if result["requires_approval"]:
            message = (
                "Registration successful! Your account is pending admin approval. "
                "You will be notified once your access is granted."
            )
        else:
            message = (
                "Registration successful! You now have full access. "
                "You can sign in with your credentials."
            )

        return UserRegistrationResponse(
            user_id=result["user_id"],
            email=result["email"],
            role=result["role"],
            requires_approval=result["requires_approval"],
            message=message,
        )
    except ImportError:
        raise HTTPException(
            status_code=501,
            detail="Registration requires Keycloak. Set AUTH_BYPASS=true for dev mode or configure Keycloak.",
        )
    except Exception as e:
        log.error(f"Registration failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/pending-status")
async def get_pending_status(user: dict = Depends(get_current_user)):
    """
    Check if the current user is pending approval.
    Returns the user's status and whether they need admin approval.
    """
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    roles = user.get("realm_access", {}).get("roles", [])
    is_pending = "pending" in roles and "user" not in roles and "admin" not in roles

    return {
        "is_pending": is_pending,
        "roles": roles,
        "message": (
            "Your account is awaiting admin approval."
            if is_pending
            else "Your account is active."
        ),
    }
