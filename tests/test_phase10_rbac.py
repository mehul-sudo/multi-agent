"""
Tests for Phase 10 RBAC and Fine-Grained Permission Enforcement.
"""

import pytest
from app.models.permission import (
    PERM_WORKFLOW_CREATE,
    PERM_WORKFLOW_DELETE,
    PERM_AUDIT_LOG_READ,
    ROLE_PLATFORM_ADMIN,
    ROLE_ORG_ADMIN,
    ROLE_WORKFLOW_OWNER,
    ROLE_AUDITOR,
    ROLE_USER,
    ROLE_READONLY,
)
from app.services.permission_service import PermissionService


def test_platform_admin_has_all_permissions(db_session, user_factory):
    admin = user_factory(role=ROLE_PLATFORM_ADMIN)
    assert PermissionService.has_permission(admin, PERM_WORKFLOW_CREATE) is True
    assert PermissionService.has_permission(admin, PERM_WORKFLOW_DELETE) is True
    assert PermissionService.has_permission(admin, PERM_AUDIT_LOG_READ) is True


def test_auditor_role_permissions(db_session, user_factory):
    auditor = user_factory(role=ROLE_AUDITOR)
    assert PermissionService.has_permission(auditor, PERM_AUDIT_LOG_READ) is True
    assert PermissionService.has_permission(auditor, PERM_WORKFLOW_CREATE) is False
    assert PermissionService.has_permission(auditor, PERM_WORKFLOW_DELETE) is False


def test_readonly_user_permissions(db_session, user_factory):
    ro_user = user_factory(role=ROLE_READONLY)
    assert PermissionService.has_permission(ro_user, PERM_WORKFLOW_CREATE) is False
    assert PermissionService.has_permission(ro_user, PERM_WORKFLOW_DELETE) is False


def test_owner_permission_check(db_session, user_factory):
    owner = user_factory(role=ROLE_USER)
    other_user = user_factory(role=ROLE_USER)

    # Owner should pass check even if not platform admin
    assert PermissionService.check_permission(owner, PERM_WORKFLOW_DELETE, resource_owner_id=owner.id) is True
    # Other user should fail if resource_owner_id does not match and permission is lacking
    assert PermissionService.check_permission(other_user, PERM_WORKFLOW_DELETE, resource_owner_id=owner.id) is False
