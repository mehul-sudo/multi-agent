"""
User model.

Represents an account in the system. Passwords are never stored in
plaintext - only a hash (see app/security/password.py). Internal
numeric IDs are never exposed through the API; `public_id` is used for
all external references instead.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint

from app.extensions import db

ROLE_USER = "user"
ROLE_ADMIN = "admin"
ROLE_MANAGER = "manager"
ROLE_PLATFORM_ADMIN = "platform_admin"
ROLE_ORG_ADMIN = "org_admin"
ROLE_WORKFLOW_OWNER = "workflow_owner"
ROLE_WORKFLOW_OPERATOR = "workflow_operator"
ROLE_AGENT_MANAGER = "agent_manager"
ROLE_AUDITOR = "auditor"
ROLE_READONLY = "readonly"

SUPPORTED_ROLES = (
    ROLE_USER,
    ROLE_ADMIN,
    ROLE_MANAGER,
    ROLE_PLATFORM_ADMIN,
    ROLE_ORG_ADMIN,
    ROLE_WORKFLOW_OWNER,
    ROLE_WORKFLOW_OPERATOR,
    ROLE_AGENT_MANAGER,
    ROLE_AUDITOR,
    ROLE_READONLY,
)



def _utcnow() -> datetime:
    """Return a naive UTC datetime for storage.

    SQLite does not preserve timezone info reliably, so timestamps are
    stored as naive UTC and treated as UTC by convention everywhere in
    this project.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(db.Model):
    """A user account.

    Note: this model only defines storage and constraints. Password
    hashing lives in app/security/password.py, input validation lives
    in app/schemas/user.py, and all database operations should go
    through app/services/user_service.py rather than touching the
    model directly from route handlers.
    """

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            f"role IN {SUPPORTED_ROLES}",
            name="ck_users_role_valid",
        ),
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    public_id = db.Column(
        db.String(36),
        unique=True,
        index=True,
        nullable=False,
        default=lambda: str(uuid.uuid4()),
    )

    username = db.Column(db.String(64), unique=True, index=True, nullable=False)
    email = db.Column(db.String(255), unique=True, index=True, nullable=False)

    # Never returned via the API. Only written by
    # app/security/password.py's hash_password() output.
    password_hash = db.Column(db.String(255), nullable=False)

    first_name = db.Column(db.String(100), nullable=True)
    last_name = db.Column(db.String(100), nullable=True)

    role = db.Column(db.String(20), nullable=False, default=ROLE_USER)

    is_active = db.Column(db.Boolean, nullable=False, default=True)
    is_verified = db.Column(db.Boolean, nullable=False, default=False)

    last_login_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=_utcnow, onupdate=_utcnow
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid only
        return f"<User public_id={self.public_id} username={self.username!r}>"
