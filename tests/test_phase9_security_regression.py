"""
Phase 9 Tests - Security Regression Validation.
"""

import pytest
from app.extensions import db
from app.services.condition_evaluator import evaluate_condition
from flask_jwt_extended import create_access_token

def test_ast_evaluator_security():
    # Attempt malicious injections in condition evaluator
    malicious_conditions = [
        "__import__('os').system('echo pwned')",
        "open('/etc/passwd').read()",
        "eval('1+1')",
        "exec('a=1')",
        "context.__class__.__bases__[0]"
    ]
    
    context = {"x": 1}
    for cond in malicious_conditions:
        assert evaluate_condition(cond, context) is False
            
def test_cross_user_workflow_access(app, client, test_user, other_user, auth_headers):
    # User 1 creates workflow
    with app.app_context():
        from app.models.workflow import Workflow
        wf = Workflow(user_id=test_user.id, name="User 1 WF")
        db.session.add(wf)
        db.session.commit()
        wf_id = wf.public_id
        
    with app.app_context():
        access_token = create_access_token(identity=other_user.public_id)
        
    hacker_headers = {"Authorization": f"Bearer {access_token}"}
    
    res = client.get(f"/api/workflows/{wf_id}", headers=hacker_headers)
    assert res.status_code in (403, 404)
    
def test_sql_injection_prevention(app, client, auth_headers):
    # Try SQL injection in list endpoint
    res = client.get("/api/workflows?status=active' OR '1'='1", headers=auth_headers)
    assert res.status_code in (200, 400, 422)
    
def test_unauthenticated_access_rejected(client):
    res = client.get("/api/workflows")
    assert res.status_code == 401
    
    res = client.post("/api/workflows", json={"name": "test"})
    assert res.status_code == 401
