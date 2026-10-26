"""
RBAC enforcement tests (Phase 10 hardening).

These exercise the governance endpoints over HTTP to prove that the
@require_permission decorator is actually wired in and fails closed:
  - no token            -> 401
  - authenticated 'user' -> 403 (lacks the manage permission)
  - authenticated admin  -> success

Before this hardening these endpoints only required a valid token, so any
authenticated user could create or read governance policies.
"""


# ---------------------------------------------------------------------------
# Tool policies (PERM_TOOL_POLICY_MANAGE)
# ---------------------------------------------------------------------------


def test_create_tool_policy_requires_authentication(client):
    res = client.post("/api/v1/tool-policies", json={"name": "p", "tool_name": "t"})
    assert res.status_code == 401


def test_create_tool_policy_forbidden_for_regular_user(client, auth_headers):
    res = client.post(
        "/api/v1/tool-policies",
        json={"name": "p", "tool_name": "shell"},
        headers=auth_headers,
    )
    assert res.status_code == 403


def test_create_tool_policy_allowed_for_admin(client, admin_auth_headers):
    res = client.post(
        "/api/v1/tool-policies",
        json={"name": "shell-policy", "tool_name": "shell", "is_dangerous": True},
        headers=admin_auth_headers,
    )
    assert res.status_code == 201
    assert res.get_json()["policy"]["name"] == "shell-policy"


def test_list_tool_policies_forbidden_for_regular_user(client, auth_headers):
    res = client.get("/api/v1/tool-policies", headers=auth_headers)
    assert res.status_code == 403


def test_list_tool_policies_allowed_for_admin(client, admin_auth_headers):
    res = client.get("/api/v1/tool-policies", headers=admin_auth_headers)
    assert res.status_code == 200
    assert "policies" in res.get_json()


# ---------------------------------------------------------------------------
# Workflow policies (PERM_POLICY_MANAGE)
# ---------------------------------------------------------------------------


def test_create_workflow_policy_requires_authentication(client):
    res = client.post("/api/v1/workflow-policies", json={"name": "wp"})
    assert res.status_code == 401


def test_create_workflow_policy_forbidden_for_regular_user(client, auth_headers):
    res = client.post(
        "/api/v1/workflow-policies",
        json={"name": "wp"},
        headers=auth_headers,
    )
    assert res.status_code == 403


def test_create_workflow_policy_allowed_for_admin(client, admin_auth_headers):
    res = client.post(
        "/api/v1/workflow-policies",
        json={"name": "budget-policy", "token_budget": 5000},
        headers=admin_auth_headers,
    )
    assert res.status_code == 201
    assert res.get_json()["policy"]["name"] == "budget-policy"


def test_list_workflow_policies_forbidden_for_regular_user(client, auth_headers):
    res = client.get("/api/v1/workflow-policies", headers=auth_headers)
    assert res.status_code == 403


def test_list_workflow_policies_allowed_for_admin(client, admin_auth_headers):
    res = client.get("/api/v1/workflow-policies", headers=admin_auth_headers)
    assert res.status_code == 200
    assert "policies" in res.get_json()
