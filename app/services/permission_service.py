"""
Permission Evaluation Service.

Provides backend-enforced Role-Based Access Control (RBAC) and fine-grained
permission checks for users and organization members.
"""

from functools import wraps
from typing import Callable, Optional, Set

from flask import jsonify
from flask_jwt_extended import current_user

from app.models.organization import OrganizationMember
from app.models.permission import (
    ALL_PERMISSIONS,
    ROLE_ADMIN,
    ROLE_PERMISSIONS,
    ROLE_PLATFORM_ADMIN,
    ROLE_USER,
)
from app.models.user import User


class PermissionService:
    """Service for evaluating roles, fine-grained permissions, and ownership."""

    @staticmethod
    def get_user_permissions(user: User, organization_id: Optional[int] = None) -> Set[str]:
        """Resolve all effective permissions for a user globally or within an organization."""
        if not user or not user.is_active:
            return set()

        # Platform Admin or Admin role gets ALL permissions
        if user.role in (ROLE_PLATFORM_ADMIN, ROLE_ADMIN):
            return set(ALL_PERMISSIONS)

        permissions = set()

        # Add base platform role permissions (e.g. user, manager)
        platform_perms = ROLE_PERMISSIONS.get(user.role, set())
        permissions.update(platform_perms)

        # If organization context is provided, combine org membership permissions
        if organization_id:
            membership = OrganizationMember.query.filter_by(
                organization_id=organization_id, user_id=user.id, is_active=True
            ).first()
            if membership:
                org_perms = ROLE_PERMISSIONS.get(membership.org_role, set())
                permissions.update(org_perms)

        return permissions

    @classmethod
    def has_permission(
        cls,
        user: User,
        permission: str,
        organization_id: Optional[int] = None,
    ) -> bool:
        """Check if user possesses a specific permission."""
        if not user or not user.is_active:
            return False

        user_perms = cls.get_user_permissions(user, organization_id=organization_id)
        return permission in user_perms

    @classmethod
    def check_permission(
        cls,
        user: User,
        permission: str,
        organization_id: Optional[int] = None,
        resource_owner_id: Optional[int] = None,
    ) -> bool:
        """Check if user has permission OR is the owner of the resource."""
        if not user or not user.is_active:
            return False

        # Platform/Org admin bypass
        if user.role in (ROLE_PLATFORM_ADMIN, ROLE_ADMIN):
            return True

        # Resource ownership match
        if resource_owner_id is not None and user.id == resource_owner_id:
            return True

        return cls.has_permission(user, permission, organization_id=organization_id)


def require_permission(permission: str, get_org_id_func: Optional[Callable] = None):
    """Decorator to enforce fine-grained permissions on API endpoints."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not current_user:
                return jsonify({"error": "Unauthorized", "message": "Authentication required"}), 401

            org_id = None
            if get_org_id_func:
                try:
                    org_id = get_org_id_func(*args, **kwargs)
                except Exception:
                    org_id = None

            if not PermissionService.has_permission(current_user, permission, organization_id=org_id):
                return jsonify({
                    "error": "Forbidden",
                    "message": f"Permission '{permission}' required for this resource",
                }), 403

            return fn(*args, **kwargs)
        return wrapper
    return decorator
