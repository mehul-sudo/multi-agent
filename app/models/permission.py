"""
Permission definitions and Role-Permission mapping.

Provides centralized permission constants and role assignment maps
for Phase 10 RBAC and fine-grained authorization checks.
"""

# ---------------------------------------------------------------------------
# Permission Constants
# ---------------------------------------------------------------------------

# Workflow Permissions
PERM_WORKFLOW_CREATE = "workflow:create"
PERM_WORKFLOW_READ = "workflow:read"
PERM_WORKFLOW_UPDATE = "workflow:update"
PERM_WORKFLOW_DELETE = "workflow:delete"
PERM_WORKFLOW_EXECUTE = "workflow:execute"
PERM_WORKFLOW_CANCEL = "workflow:cancel"
PERM_WORKFLOW_SCHEDULE = "workflow:schedule"

# Agent Permissions
PERM_AGENT_CREATE = "agent:create"
PERM_AGENT_READ = "agent:read"
PERM_AGENT_UPDATE = "agent:update"
PERM_AGENT_DELETE = "agent:delete"
PERM_AGENT_MANAGE = "agent:manage"

# Tool Permissions
PERM_TOOL_EXECUTE = "tool:execute"
PERM_TOOL_POLICY_MANAGE = "tool:policy_manage"

# Credential Vault Permissions
PERM_CREDENTIAL_READ = "credential:read"
PERM_CREDENTIAL_WRITE = "credential:write"
PERM_CREDENTIAL_DELETE = "credential:delete"
PERM_CREDENTIAL_ROTATE = "credential:rotate"

# Approval Permissions
PERM_APPROVAL_CREATE = "approval:create"
PERM_APPROVAL_MANAGE = "approval:manage"

# Audit Log Permissions
PERM_AUDIT_LOG_READ = "audit:read"
PERM_AUDIT_LOG_EXPORT = "audit:export"

# Organization Management Permissions
PERM_ORG_MANAGE = "org:manage"
PERM_ORG_MEMBER_MANAGE = "org:member_manage"

# Security Policy Permissions
PERM_POLICY_MANAGE = "policy:manage"

# System Administration
PERM_SYSTEM_ADMIN = "system:admin"

ALL_PERMISSIONS = {
    PERM_WORKFLOW_CREATE,
    PERM_WORKFLOW_READ,
    PERM_WORKFLOW_UPDATE,
    PERM_WORKFLOW_DELETE,
    PERM_WORKFLOW_EXECUTE,
    PERM_WORKFLOW_CANCEL,
    PERM_WORKFLOW_SCHEDULE,
    PERM_AGENT_CREATE,
    PERM_AGENT_READ,
    PERM_AGENT_UPDATE,
    PERM_AGENT_DELETE,
    PERM_AGENT_MANAGE,
    PERM_TOOL_EXECUTE,
    PERM_TOOL_POLICY_MANAGE,
    PERM_CREDENTIAL_READ,
    PERM_CREDENTIAL_WRITE,
    PERM_CREDENTIAL_DELETE,
    PERM_CREDENTIAL_ROTATE,
    PERM_APPROVAL_CREATE,
    PERM_APPROVAL_MANAGE,
    PERM_AUDIT_LOG_READ,
    PERM_AUDIT_LOG_EXPORT,
    PERM_ORG_MANAGE,
    PERM_ORG_MEMBER_MANAGE,
    PERM_POLICY_MANAGE,
    PERM_SYSTEM_ADMIN,
}

# ---------------------------------------------------------------------------
# Role Definitions & Mappings
# ---------------------------------------------------------------------------

ROLE_PLATFORM_ADMIN = "platform_admin"
ROLE_ORG_ADMIN = "org_admin"
ROLE_WORKFLOW_OWNER = "workflow_owner"
ROLE_WORKFLOW_OPERATOR = "workflow_operator"
ROLE_AGENT_MANAGER = "agent_manager"
ROLE_AUDITOR = "auditor"
ROLE_USER = "user"
ROLE_READONLY = "readonly"
ROLE_ADMIN = "admin"
ROLE_MANAGER = "manager"

# Role permissions definition dictionary
ROLE_PERMISSIONS = {
    ROLE_PLATFORM_ADMIN: ALL_PERMISSIONS,
    ROLE_ADMIN: ALL_PERMISSIONS,  # Backward compatibility with existing user.role="admin"
    ROLE_ORG_ADMIN: {
        PERM_WORKFLOW_CREATE,
        PERM_WORKFLOW_READ,
        PERM_WORKFLOW_UPDATE,
        PERM_WORKFLOW_DELETE,
        PERM_WORKFLOW_EXECUTE,
        PERM_WORKFLOW_CANCEL,
        PERM_WORKFLOW_SCHEDULE,
        PERM_AGENT_CREATE,
        PERM_AGENT_READ,
        PERM_AGENT_UPDATE,
        PERM_AGENT_DELETE,
        PERM_AGENT_MANAGE,
        PERM_TOOL_EXECUTE,
        PERM_TOOL_POLICY_MANAGE,
        PERM_CREDENTIAL_READ,
        PERM_CREDENTIAL_WRITE,
        PERM_CREDENTIAL_DELETE,
        PERM_CREDENTIAL_ROTATE,
        PERM_APPROVAL_CREATE,
        PERM_APPROVAL_MANAGE,
        PERM_AUDIT_LOG_READ,
        PERM_AUDIT_LOG_EXPORT,
        PERM_ORG_MANAGE,
        PERM_ORG_MEMBER_MANAGE,
        PERM_POLICY_MANAGE,
    },
    ROLE_WORKFLOW_OWNER: {
        PERM_WORKFLOW_CREATE,
        PERM_WORKFLOW_READ,
        PERM_WORKFLOW_UPDATE,
        PERM_WORKFLOW_DELETE,
        PERM_WORKFLOW_EXECUTE,
        PERM_WORKFLOW_CANCEL,
        PERM_WORKFLOW_SCHEDULE,
        PERM_AGENT_READ,
        PERM_TOOL_EXECUTE,
        PERM_APPROVAL_CREATE,
        PERM_AUDIT_LOG_READ,
    },
    ROLE_WORKFLOW_OPERATOR: {
        PERM_WORKFLOW_READ,
        PERM_WORKFLOW_EXECUTE,
        PERM_WORKFLOW_CANCEL,
        PERM_WORKFLOW_SCHEDULE,
        PERM_AGENT_READ,
        PERM_TOOL_EXECUTE,
        PERM_APPROVAL_CREATE,
    },
    ROLE_AGENT_MANAGER: {
        PERM_AGENT_CREATE,
        PERM_AGENT_READ,
        PERM_AGENT_UPDATE,
        PERM_AGENT_DELETE,
        PERM_AGENT_MANAGE,
        PERM_TOOL_EXECUTE,
        PERM_TOOL_POLICY_MANAGE,
        PERM_WORKFLOW_READ,
    },
    ROLE_AUDITOR: {
        PERM_AUDIT_LOG_READ,
        PERM_AUDIT_LOG_EXPORT,
        PERM_WORKFLOW_READ,
        PERM_AGENT_READ,
    },
    ROLE_MANAGER: {  # Backward compatibility with existing user.role="manager"
        PERM_WORKFLOW_CREATE,
        PERM_WORKFLOW_READ,
        PERM_WORKFLOW_UPDATE,
        PERM_WORKFLOW_EXECUTE,
        PERM_WORKFLOW_CANCEL,
        PERM_WORKFLOW_SCHEDULE,
        PERM_AGENT_CREATE,
        PERM_AGENT_READ,
        PERM_AGENT_UPDATE,
        PERM_AGENT_MANAGE,
        PERM_TOOL_EXECUTE,
        PERM_APPROVAL_CREATE,
        PERM_APPROVAL_MANAGE,
        PERM_AUDIT_LOG_READ,
    },
    ROLE_USER: {
        PERM_WORKFLOW_CREATE,
        PERM_WORKFLOW_READ,
        PERM_WORKFLOW_UPDATE,
        PERM_WORKFLOW_EXECUTE,
        PERM_WORKFLOW_CANCEL,
        PERM_WORKFLOW_SCHEDULE,
        PERM_AGENT_READ,
        PERM_TOOL_EXECUTE,
        PERM_APPROVAL_CREATE,
    },
    ROLE_READONLY: {
        PERM_WORKFLOW_READ,
        PERM_AGENT_READ,
        PERM_AUDIT_LOG_READ,
    },
}
