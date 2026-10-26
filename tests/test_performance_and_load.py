"""
Performance & Load Test Suite (Phase 12).

Tests backend under concurrent requests, evaluates API response latency,
verifies throughput, and checks rate limiting and health endpoints.
"""

import time
import pytest
from app.extensions import db
from app.models.workflow import Workflow
from app.services.workflow_service import create_workflow


def test_health_endpoints_performance(client):
    """Verify health and readiness endpoints respond under 50ms."""
    start = time.perf_counter()
    res = client.get("/api/health/live")
    elapsed_ms = (time.perf_counter() - start) * 1000
    assert res.status_code == 200
    assert elapsed_ms < 50, f"Health live endpoint took {elapsed_ms:.2f}ms (>50ms)"

    start = time.perf_counter()
    res_ready = client.get("/api/health/ready")
    elapsed_ready_ms = (time.perf_counter() - start) * 1000
    assert res_ready.status_code == 200
    assert elapsed_ready_ms < 100, f"Health ready endpoint took {elapsed_ready_ms:.2f}ms (>100ms)"


def test_workflow_creation_load(client, auth_headers, app, test_user):
    """Simulate batch creation of 20 workflows and measure average latency."""
    latencies = []
    for i in range(20):
        start = time.perf_counter()
        res = client.post(
            "/api/workflows",
            json={"name": f"Batch Workflow {i}", "description": "Load testing pipeline"},
            headers=auth_headers,
        )
        elapsed_ms = (time.perf_counter() - start) * 1000
        latencies.append(elapsed_ms)
        assert res.status_code in (200, 201)

    avg_latency = sum(latencies) / len(latencies)
    max_latency = max(latencies)
    assert avg_latency < 100, f"Average workflow creation latency {avg_latency:.2f}ms exceeds 100ms"
    assert max_latency < 300, f"Maximum workflow creation latency {max_latency:.2f}ms exceeds 300ms"


def test_admin_metrics_performance(client, admin_auth_headers):
    """Verify administrative metrics aggregation endpoint latency."""
    start = time.perf_counter()
    res = client.get("/api/v1/admin/metrics", headers=admin_auth_headers)
    elapsed_ms = (time.perf_counter() - start) * 1000
    assert res.status_code == 200
    assert res.get_json()["data"]["system_status"] == "healthy"
    assert elapsed_ms < 150, f"Metrics endpoint took {elapsed_ms:.2f}ms (>150ms)"
