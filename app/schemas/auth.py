"""
Authentication request schemas (Pydantic v2).

Validates input for the /api/auth endpoints. Password content is
validated only for length/type - never logged or included in error
messages.
"""

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

PASSWORD_MIN_LENGTH = 8


class LoginSchema(BaseModel):
    """Input for POST /api/auth/login."""

    model_config = ConfigDict(extra="ignore")

    email: EmailStr
    password: str = Field(min_length=1)  # presence check; hash check handles correctness

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.lower()


class ChangePasswordSchema(BaseModel):
    """Input for POST /api/auth/change-password."""

    model_config = ConfigDict(extra="ignore")

    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=PASSWORD_MIN_LENGTH)
