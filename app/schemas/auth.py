# app/schemas/auth.py
"""
Pydantic schemas for authentication and registration.
"""

from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class UserRegistration(BaseModel):
    """Request model for user self-registration."""

    email: EmailStr
    password: str = Field(
        ..., min_length=8, description="Password must be at least 8 characters"
    )
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)


class UserRegistrationResponse(BaseModel):
    """Response model for successful registration."""

    user_id: str
    email: str
    role: str
    requires_approval: bool
    message: str
    temporary_password: Optional[str] = None  # Only returned for admin-created users


class PendingStatusResponse(BaseModel):
    """Response model for pending status check."""

    is_pending: bool
    roles: list[str]
    message: str
