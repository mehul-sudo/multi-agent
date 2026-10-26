"""
Organization and OrganizationMember models.

Provides multi-tenant organization boundaries and user memberships.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import CheckConstraint

from app.extensions import db

ORG_ROLE_ADMIN = "org_admin"
ORG_ROLE_WORKFLOW_OWNER = "workflow_owner"
ORG_ROLE_OPERATOR = "workflow_operator"
ORG_ROLE_AGENT_MANAGER = "agent_manager"
ORG_ROLE_AUDITOR = "auditor"
ORG_ROLE_MEMBER = "member"
ORG_ROLE_READONLY = "readonly"

SUPPORTED_ORG_ROLES = (
    ORG_ROLE_ADMIN,
    ORG_ROLE_WORKFLOW_OWNER,
    ORG_ROLE_OPERATOR,
    ORG_ROLE_AGENT_MANAGER,
    ORG_ROLE_AUDITOR,
    ORG_ROLE_MEMBER,
    ORG_ROLE_READONLY,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Organization(db.Model):
    """An organization / workspace tenant boundary."""

    __tablename__ = "organizations"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    public_id = db.Column(
        db.String(36),
        unique=True,
        index=True,
        nullable=False,
        default=lambda: str(uuid.uuid4()),
    )

    name = db.Column(db.String(128), nullable=False)
    slug = db.Column(db.String(128), unique=True, index=True, nullable=False)
    description = db.Column(db.Text, nullable=True)

    owner_user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False, index=True
    )

    is_active = db.Column(db.Boolean, nullable=False, default=True)

    # Tenant quota & configuration limits
    max_members = db.Column(db.Integer, nullable=False, default=50)
    max_workflows = db.Column(db.Integer, nullable=False, default=100)
    max_agents = db.Column(db.Integer, nullable=False, default=20)

    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=_utcnow, onupdate=_utcnow
    )

    # Relationships
    memberships = db.relationship(
        "OrganizationMember",
        backref="organization",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    def __repr__(self) -> str:
        return f"<Organization public_id={self.public_id} slug={self.slug!r}>"


class OrganizationMember(db.Model):
    """User membership in an organization."""

    __tablename__ = "organization_members"
    __table_args__ = (
        db.UniqueConstraint("organization_id", "user_id", name="uq_org_member"),
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    organization_id = db.Column(
        db.Integer, db.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    org_role = db.Column(
        db.String(32), nullable=False, default=ORG_ROLE_MEMBER
    )
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    joined_at = db.Column(db.DateTime, nullable=False, default=_utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=_utcnow, onupdate=_utcnow
    )

    # Relationship to user
    user = db.relationship("User", backref=db.backref("org_memberships", lazy="dynamic"))

    def __repr__(self) -> str:
        return (
            f"<OrganizationMember org_id={self.organization_id} user_id={self.user_id} role={self.org_role}>"
        )
