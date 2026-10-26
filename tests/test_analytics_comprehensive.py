"""
Comprehensive Automated Tests for Analytics, Token Tracking, Cost Calculation,
Workflow Deduplication, and Historical Reporting.
"""

from datetime import datetime, timezone
import json
import pytest
from unittest.mock import MagicMock, patch

from app.extensions import db
from app.models.agent import AGENT_STATUS_ACTIVE, Agent
from app.models.async_job import AsyncWorkflowJob
from app.models.llm_usage import LLMUsageLog
from app.models.task_execution import TASK_STATUS_COMPLETED, TASK_STATUS_FAILED, TaskExecution
from app.models.workflow import Workflow
from app.models.workflow_execution import WorkflowExecution
from app.llm.contracts import LLMMessage, LLMRequest, LLMResponse, LLMUsage
from app.services.llm_usage_service import (
    MODEL_PRICING_PER_1M,
    calculate_estimated_cost,
    record_llm_usage,
    record_llm_response_usage,
)


def _get_auth_header(client, user):
    from flask_jwt_extended import create_access_token
    token = create_access_token(identity=user.public_id)
    return {"Authorization": f"Bearer {token}"}


# 1. Cost calculation with known test rates and known token counts
def test_cost_calculation_known_rates():
    """Verify exact cost calculations for verified models and rates."""
    # gpt-4o: $5.00 / 1M prompt, $15.00 / 1M completion
    # 1,000 prompt + 1,000 completion = 0.005 + 0.015 = 0.02
    cost_gpt4 = calculate_estimated_cost("gpt-4o", prompt_tokens=1000, completion_tokens=1000)
    assert cost_gpt4 == 0.02

    # gemini-flash-lite-latest: $0.075 / 1M prompt, $0.30 / 1M completion
    # 1,000,000 prompt + 1,000,000 completion = 0.075 + 0.30 = 0.375
    cost_gemini = calculate_estimated_cost("gemini-flash-lite-latest", prompt_tokens=1000000, completion_tokens=1000000)
    assert cost_gemini == 0.375

    # Mock provider: genuine 0.0 cost
    cost_mock = calculate_estimated_cost("mock-v1", prompt_tokens=5000, completion_tokens=5000)
    assert cost_mock == 0.0


# 2. Unknown pricing and missing usage metadata
def test_unknown_pricing_and_missing_metadata(app, db_session, test_user):
    """Verify unknown model pricing returns None, and missing metadata is recorded clearly."""
    with app.app_context():
        # Unknown model
        cost_unknown = calculate_estimated_cost("unknown-exotic-llm-v99", prompt_tokens=500, completion_tokens=500)
        assert cost_unknown is None

        # Record usage with missing provider metadata
        log = record_llm_usage(
            user_id=test_user.id,
            provider="gemini",
            model="gemini-unknown-model",
            prompt_tokens=0,
            completion_tokens=0,
            duration_ms=250,
            error_category="USAGE_METADATA_UNAVAILABLE",
            allow_mock=True,
        )
        assert log is not None
        assert log.total_tokens == 0
        assert log.estimated_cost_usd is None
        assert log.error_category == "USAGE_METADATA_UNAVAILABLE"


# 3. Correct aggregation of prompt, completion, and total tokens on /usage
def test_analytics_usage_aggregation(client, test_user, app, db_session):
    """Verify prompt, completion, and total tokens are correctly aggregated on /api/v1/analytics/usage."""
    with app.app_context():
        # Create 2 usage logs
        record_llm_usage(
            user_id=test_user.id,
            provider="gemini",
            model="gemini-flash-lite-latest",
            prompt_tokens=150,
            completion_tokens=50,
            duration_ms=300,
            allow_mock=True,
        )
        record_llm_usage(
            user_id=test_user.id,
            provider="gemini",
            model="gemini-flash-lite-latest",
            prompt_tokens=300,
            completion_tokens=100,
            duration_ms=450,
            allow_mock=True,
        )

        headers = _get_auth_header(client, test_user)
        resp = client.get("/api/v1/analytics/usage", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()["data"]

        assert data["prompt_tokens"] == 450
        assert data["completion_tokens"] == 150
        assert data["total_tokens"] == 600
        assert data["record_count"] >= 2
        assert data["total_tokens"] == data["prompt_tokens"] + data["completion_tokens"]


# 4. Provider and model cost aggregation on /costs
def test_analytics_cost_aggregation(client, test_user, app, db_session):
    """Verify costs are aggregated by provider and model accurately on /api/v1/analytics/costs."""
    with app.app_context():
        record_llm_usage(
            user_id=test_user.id,
            provider="openai",
            model="gpt-4o",
            prompt_tokens=1000,
            completion_tokens=1000,
            duration_ms=500,
            allow_mock=True,
        )

        headers = _get_auth_header(client, test_user)
        resp = client.get("/api/v1/analytics/costs", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()["data"]

        assert "breakdown" in data
        assert data["total_estimated_cost_usd"] > 0
        gpt4_entry = next((b for b in data["breakdown"] if b["model"] == "gpt-4o"), None)
        assert gpt4_entry is not None
        assert gpt4_entry["prompt_tokens"] == 1000
        assert gpt4_entry["completion_tokens"] == 1000
        assert gpt4_entry["estimated_cost_usd"] == 0.02
        assert gpt4_entry["pricing_available"] is True


# 5. Per-agent aggregation on /agents (and fix for agent.is_active 500 error)
def test_analytics_agent_stats(client, test_user, app, db_session):
    """Verify /api/v1/analytics/agents aggregates per-agent metrics without crashing."""
    with app.app_context():
        agent = Agent(
            user_id=test_user.id,
            name="Analytics Audit Agent",
            role="Data Analyst",
            agent_type="data_analysis",
            status=AGENT_STATUS_ACTIVE,
            system_instructions="Perform analysis",
        )
        db.session.add(agent)
        db.session.commit()

        wf = Workflow(user_id=test_user.id, name="Agent Test WF", description="Testing")
        db.session.add(wf)
        db.session.commit()

        wf_exec = WorkflowExecution(
            user_id=test_user.id,
            workflow_id=wf.id,
            status="completed",
        )
        db.session.add(wf_exec)
        db.session.commit()

        # Add an execution and an LLM log for this agent
        task_exec = TaskExecution(
            workflow_execution_id=wf_exec.id,
            agent_id=agent.id,
            status=TASK_STATUS_COMPLETED,
            duration_ms=120,
        )
        db.session.add(task_exec)
        db.session.commit()

        record_llm_usage(
            user_id=test_user.id,
            agent_id=agent.id,
            provider="gemini",
            model="gemini-flash-lite-latest",
            prompt_tokens=200,
            completion_tokens=80,
            duration_ms=250,
            allow_mock=True,
        )

        headers = _get_auth_header(client, test_user)
        resp = client.get("/api/v1/analytics/agents", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()["data"]

        ag_stat = next((a for a in data["agents"] if a["name"] == "Analytics Audit Agent"), None)
        assert ag_stat is not None
        assert ag_stat["status"] == "active"
        assert ag_stat["invocations"] >= 1
        assert ag_stat["successes"] >= 1
        assert ag_stat["prompt_tokens"] == 200
        assert ag_stat["completion_tokens"] == 80
        assert ag_stat["total_tokens"] == 280
        assert ag_stat["llm_calls"] >= 1


# 6. Workflow status counts and duplicate prevention
def test_workflow_status_and_duplicate_prevention(client, test_user, app, db_session):
    """Verify workflow executions and linked async jobs are not double-counted on /workflows."""
    with app.app_context():
        wf = Workflow(user_id=test_user.id, name="Test Pipeline", description="Testing")
        db.session.add(wf)
        db.session.commit()

        wf_exec = WorkflowExecution(
            user_id=test_user.id,
            workflow_id=wf.id,
            status="completed",
        )
        db.session.add(wf_exec)
        db.session.commit()

        # Linked AsyncWorkflowJob should NOT increment execution total again
        async_job_linked = AsyncWorkflowJob(
            user_id=test_user.id,
            workflow_id=wf.id,
            workflow_execution_id=wf_exec.id,
            status="SUCCEEDED",
        )
        db.session.add(async_job_linked)
        db.session.commit()

        headers = _get_auth_header(client, test_user)
        resp = client.get("/api/v1/analytics/workflows", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()["data"]

        # Exactly 1 completed job, not 2
        assert data["status_counts"].get("COMPLETED", 0) + data["status_counts"].get("SUCCEEDED", 0) == 1
        assert data["total_jobs"] == 1


# 7. Historical trends on /history
def test_analytics_historical_trends(client, test_user, app, db_session):
    """Verify /api/v1/analytics/history returns chronological daily trend records."""
    with app.app_context():
        wf = Workflow(user_id=test_user.id, name="Daily WF", description="Testing")
        db.session.add(wf)
        db.session.commit()

        wf_exec = WorkflowExecution(
            user_id=test_user.id,
            workflow_id=wf.id,
            status="completed",
        )
        db.session.add(wf_exec)
        db.session.commit()

        record_llm_usage(
            user_id=test_user.id,
            provider="gemini",
            model="gemini-flash-lite-latest",
            prompt_tokens=400,
            completion_tokens=150,
            duration_ms=300,
            allow_mock=True,
        )

        headers = _get_auth_header(client, test_user)
        resp = client.get("/api/v1/analytics/history?days=7", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()["data"]

        assert data["period_days"] == 7
        assert "trends" in data
        assert len(data["trends"]) >= 1
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        today_trend = next((t for t in data["trends"] if t["date"] == today_str), None)
        assert today_trend is not None
        assert today_trend["total_tokens"] >= 550
        assert today_trend["workflow_executions"] >= 1


# 8. Deduplication across refreshes and retries
def test_usage_deduplication(app, db_session, test_user):
    """Verify identical provider response is not duplicated in usage logs."""
    with app.app_context():
        dedup_id = "test-dedup-uuid-1234"
        log1 = record_llm_usage(
            user_id=test_user.id,
            provider="gemini",
            model="gemini-flash-lite-latest",
            prompt_tokens=100,
            completion_tokens=50,
            duration_ms=200,
            dedup_key=dedup_id,
            allow_mock=True,
        )
        log2 = record_llm_usage(
            user_id=test_user.id,
            provider="gemini",
            model="gemini-flash-lite-latest",
            prompt_tokens=100,
            completion_tokens=50,
            duration_ms=200,
            dedup_key=dedup_id,
            allow_mock=True,
        )
        assert log1.id == log2.id
        count = LLMUsageLog.query.filter_by(public_id=dedup_id).count()
        assert count == 1


# 9. Authentication required on all analytics endpoints
def test_analytics_authentication_required(client):
    """Verify unauthorized requests without Bearer token are rejected with 401."""
    for endpoint in ["usage", "costs", "workflows", "agents", "history", "summary"]:
        resp = client.get(f"/api/v1/analytics/{endpoint}")
        assert resp.status_code == 401


# 10. Live Gemini Provider generation and usage metadata extraction
def test_gemini_adapter_usage_metadata_parsing():
    """Verify GeminiProviderAdapter accurately extracts usage_metadata without fabricating tokens."""
    from app.llm.providers.gemini_adapter import GeminiProviderAdapter

    adapter = GeminiProviderAdapter(api_key="mock-key-for-test")

    # Case A: Response contains verified usage_metadata
    mock_resp_with_meta = MagicMock()
    mock_resp_with_meta.text = "Analysis completed."
    mock_usage = MagicMock()
    mock_usage.prompt_token_count = 142
    mock_usage.candidates_token_count = 38
    mock_usage.total_token_count = 180
    mock_resp_with_meta.usage_metadata = mock_usage

    parsed_a = adapter._parse_gemini_response(mock_resp_with_meta, "gemini-flash-lite-latest", start_time=0.0)
    assert parsed_a.usage.prompt_tokens == 142
    assert parsed_a.usage.completion_tokens == 38
    assert parsed_a.usage.total_tokens == 180
    assert parsed_a.usage.metadata_available is True

    # Case B: Response missing usage_metadata - MUST NOT fabricate tokens with len(text.split())
    mock_resp_no_meta = MagicMock()
    mock_resp_no_meta.text = "Ten words in this string that must not become tokens count."
    mock_resp_no_meta.usage_metadata = None

    parsed_b = adapter._parse_gemini_response(mock_resp_no_meta, "gemini-flash-lite-latest", start_time=0.0)
    assert parsed_b.usage.prompt_tokens == 0
    assert parsed_b.usage.completion_tokens == 0
    assert parsed_b.usage.total_tokens == 0
    assert parsed_b.usage.metadata_available is False
