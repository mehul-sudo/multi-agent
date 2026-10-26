"""
Tests for Phase 10 Organization and Tenant Isolation.
"""

import pytest
from app.services.organization_service import OrganizationService


def test_create_organization(db_session, user_factory):
    user = user_factory()
    org = OrganizationService.create_organization(
        name="Acme Corp",
        slug="acme-corp",
        owner_user_id=user.id,
    )
    assert org.id is not None
    assert org.name == "Acme Corp"
    assert org.owner_user_id == user.id

    membership = OrganizationService.get_user_org_membership(org.id, user.id)
    assert membership is not None
    assert membership.org_role == "org_admin"


def test_tenant_isolation_validation(db_session, user_factory):
    user1 = user_factory()
    user2 = user_factory()

    org = OrganizationService.create_organization(
        name="TechCorp",
        slug="techcorp",
        owner_user_id=user1.id,
    )

    # User 1 belongs to org
    assert OrganizationService.validate_tenant_access(user1.id, org.id) is True
    # User 2 does NOT belong to org
    assert OrganizationService.validate_tenant_access(user2.id, org.id) is False


def test_add_and_remove_org_member(db_session, user_factory):
    owner = user_factory()
    member_user = user_factory()

    org = OrganizationService.create_organization(
        name="Global Logistics",
        slug="global-logistics",
        owner_user_id=owner.id,
    )

    member = OrganizationService.add_member(org.id, member_user.id, org_role="workflow_operator")
    assert member.user_id == member_user.id
    assert OrganizationService.validate_tenant_access(member_user.id, org.id) is True

    # Remove member
    success = OrganizationService.remove_member(org.id, member_user.id)
    assert success is True
    assert OrganizationService.validate_tenant_access(member_user.id, org.id) is False
