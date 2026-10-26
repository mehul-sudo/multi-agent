"""
User request/response schemas (Pydantic v2).

These schemas define the *only* fields a client can supply or receive
for user-related endpoints. In particular, `UserCreateSchema` and
`UserUpdateSchema` deliberately omit `role`, `is_active`, and
`is_verified` - those are never client-controlled in this phase, so a
normal user cannot elevate their own privileges through request data.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

USERNAME_MIN_LENGTH = 3
USERNAME_MAX_LENGTH = 64
PASSWORD_MIN_LENGTH = 8


class UserCreateSchema(BaseModel):
    """Input for POST /api/users. Only these fields are accepted -
    role/is_active/is_verified are never user-controlled here.
    """

    username: str = Field(min_length=USERNAME_MIN_LENGTH, max_length=USERNAME_MAX_LENGTH)
    email: EmailStr
    password: str = Field(min_length=PASSWORD_MIN_LENGTH)
    first_name: Optional[str] = Field(default=None, max_length=100)
    last_name: Optional[str] = Field(default=None, max_length=100)

    @field_validator("username")
    @classmethod
    def username_not_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Username must not be blank.")
        return stripped

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.lower()


class UserUpdateSchema(BaseModel):
    """Input for PATCH /api/users/<public_id>.

    Only safe profile fields are accepted. role, password_hash,
    is_active, is_verified, public_id, created_at, and updated_at are
    intentionally absent - they cannot be set through this schema no
    matter what the client sends.
    """

    model_config = ConfigDict(extra="ignore")

    username: Optional[str] = Field(
        default=None, min_length=USERNAME_MIN_LENGTH, max_length=USERNAME_MAX_LENGTH
    )
    first_name: Optional[str] = Field(default=None, max_length=100)
    last_name: Optional[str] = Field(default=None, max_length=100)

    @field_validator("username")
    @classmethod
    def username_not_blank(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        stripped = value.strip()
        if not stripped:
            raise ValueError("Username must not be blank.")
        return stripped


class UserResponseSchema(BaseModel):
    """Safe public representation of a user.

    Never includes password, password_hash, or any other sensitive
    internal field.
    """

    model_config = ConfigDict(from_attributes=True)

    public_id: str
    username: str
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role: str
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime


class UserListResponseSchema(BaseModel):
    """Paginated list response for GET /api/users."""

    users: list[UserResponseSchema]
    page: int
    per_page: int
    total: int
    pages: int
