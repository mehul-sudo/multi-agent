"""
Organization Service.

Provides organization CRUD, tenant isolation helpers, membership management,
and user role mapping within organizations.
"""

from typing import Dict, List, Optional, Tuple

from app.extensions import db
from app.models.organization import (
    Organization,
    OrganizationMember,
    ORG_ROLE_ADMIN,
    ORG_ROLE_MEMBER,
    SUPPORTED_ORG_ROLES,
)
from app.models.user import User


class OrganizationService:
    """Service for managing organizations, memberships, and tenant scope."""

    @staticmethod
    def create_organization(
        name: str,
        slug: str,
        owner_user_id: int,
        description: Optional[str] = None,
        max_members: int = 50,
        max_workflows: int = 100,
        max_agents: int = 20,
    ) -> Organization:
        """Create a new organization and assign the creator as owner/admin member."""
        existing = Organization.query.filter_by(slug=slug).first()
        if existing:
            raise ValueError(f"Organization with slug '{slug}' already exists")

        owner = User.query.get(owner_user_id)
        if not owner:
            raise ValueError("Owner user does not exist")

        org = Organization(
            name=name,
            slug=slug,
            owner_user_id=owner_user_id,
            description=description,
            max_members=max_members,
            max_workflows=max_workflows,
            max_agents=max_agents,
        )
        db.session.add(org)
        db.session.flush()

        # Automatically add owner as ORG_ROLE_ADMIN member
        membership = OrganizationMember(
            organization_id=org.id,
            user_id=owner_user_id,
            org_role=ORG_ROLE_ADMIN,
            is_active=True,
        )
        db.session.add(membership)
        db.session.commit()
        return org

    @staticmethod
    def get_organization_by_public_id(public_id: str) -> Optional[Organization]:
        """Fetch organization by public_id."""
        return Organization.query.filter_by(public_id=public_id).first()

    @staticmethod
    def get_organization_by_id(org_id: int) -> Optional[Organization]:
        """Fetch organization by internal numeric ID."""
        return Organization.query.get(org_id)

    @staticmethod
    def add_member(
        org_id: int,
        user_id: int,
        org_role: str = ORG_ROLE_MEMBER,
    ) -> OrganizationMember:
        """Add a user as a member of an organization."""
        org = Organization.query.get(org_id)
        if not org:
            raise ValueError("Organization does not exist")

        user = User.query.get(user_id)
        if not user:
            raise ValueError("User does not exist")

        if org_role not in SUPPORTED_ORG_ROLES:
            raise ValueError(f"Invalid org_role '{org_role}'")

        existing_membership = OrganizationMember.query.filter_by(
            organization_id=org_id, user_id=user_id
        ).first()
        if existing_membership:
            if not existing_membership.is_active:
                existing_membership.is_active = True
                existing_membership.org_role = org_role
                db.session.commit()
                return existing_membership
            raise ValueError("User is already a member of this organization")

        # Quota check
        active_member_count = OrganizationMember.query.filter_by(
            organization_id=org_id, is_active=True
        ).count()
        if active_member_count >= org.max_members:
            raise ValueError(f"Organization member limit of {org.max_members} reached")

        membership = OrganizationMember(
            organization_id=org_id,
            user_id=user_id,
            org_role=org_role,
            is_active=True,
        )
        db.session.add(membership)
        db.session.commit()
        return membership

    @staticmethod
    def remove_member(org_id: int, user_id: int) -> bool:
        """Soft-deactivate or remove a user from an organization."""
        org = Organization.query.get(org_id)
        if org and org.owner_user_id == user_id:
            raise ValueError("Cannot remove the organization owner")

        membership = OrganizationMember.query.filter_by(
            organization_id=org_id, user_id=user_id
        ).first()
        if not membership:
            return False

        membership.is_active = False
        db.session.commit()
        return True

    @staticmethod
    def update_member_role(org_id: int, user_id: int, new_role: str) -> OrganizationMember:
        """Update a member's role within an organization."""
        if new_role not in SUPPORTED_ORG_ROLES:
            raise ValueError(f"Invalid org_role '{new_role}'")

        membership = OrganizationMember.query.filter_by(
            organization_id=org_id, user_id=user_id
        ).first()
        if not membership or not membership.is_active:
            raise ValueError("Active organization membership not found")

        membership.org_role = new_role
        db.session.commit()
        return membership

    @staticmethod
    def get_user_org_membership(org_id: int, user_id: int) -> Optional[OrganizationMember]:
        """Get active membership for a user in a specific organization."""
        return OrganizationMember.query.filter_by(
            organization_id=org_id, user_id=user_id, is_active=True
        ).first()

    @staticmethod
    def list_user_organizations(user_id: int) -> List[Organization]:
        """List all active organizations a user belongs to."""
        memberships = OrganizationMember.query.filter_by(
            user_id=user_id, is_active=True
        ).all()
        org_ids = [m.organization_id for m in memberships]
        if not org_ids:
            return []
        return Organization.query.filter(Organization.id.in_(org_ids), Organization.is_active == True).all()

    @staticmethod
    def validate_tenant_access(user_id: int, resource_org_id: Optional[int]) -> bool:
        """Validate if a user has access to a tenant-scoped resource.
        
        If resource_org_id is None (unscoped/legacy), access is permitted based on user ownership.
        If resource_org_id is set, user must be an active member of that organization.
        """
        if resource_org_id is None:
            return True

        membership = OrganizationMember.query.filter_by(
            organization_id=resource_org_id, user_id=user_id, is_active=True
        ).first()
        return membership is not None
