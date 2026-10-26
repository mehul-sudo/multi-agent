"""Health check endpoints."""

from flask import Blueprint, jsonify

from app.services.db_health import is_database_available

health_bp = Blueprint("health", __name__)

SERVICE_NAME = "multi-agent-ai-assistant"
SERVICE_VERSION = "0.1.0"


@health_bp.route("/health", methods=["GET"])
def health():
    """Basic liveness check.

    Returns a static JSON payload confirming the service is running.
    Deliberately does NOT touch the database, so this endpoint keeps
    passing even if PostgreSQL is not running - use
    GET /api/health/database to check connectivity specifically.
    """
    return (
        jsonify(
            {
                "status": "ok",
                "service": SERVICE_NAME,
                "version": SERVICE_VERSION,
            }
        ),
        200,
    )


@health_bp.route("/health/database", methods=["GET"])
def health_database():
    """Database connectivity check.

    Attempts a trivial query against the configured database. Never
    exposes credentials, connection strings, or internal stack traces
    - only a structured status is returned.
    """
    if is_database_available():
        return jsonify({"status": "ok", "database": "available"}), 200

    return jsonify({"status": "error", "database": "unavailable"}), 503


@health_bp.route("/health/live", methods=["GET"])
def health_live():
    """Liveness check confirming application process is running."""
    return jsonify({
        "success": True,
        "message": "Service process is alive",
        "data": {
            "status": "alive",
            "service": SERVICE_NAME,
            "version": SERVICE_VERSION,
        },
        "error": None,
    }), 200


def _check_redis_queue_status() -> str:
    import os
    if os.getenv("CELERY_TASK_ALWAYS_EAGER", "true").lower() in ("true", "1"):
        return "ready (in-memory)"

    try:
        import redis
        broker = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
        r = redis.Redis.from_url(broker, socket_timeout=0.1)
        if r.ping():
            return "ready"
    except Exception:
        pass

    return "degraded"


@health_bp.route("/health/ready", methods=["GET"])
def health_ready():
    """Readiness check validating underlying dependencies (Database, LLM Engine & Redis Queue)."""
    from app.services.provider_health_service import ProviderHealthManager

    db_ok = is_database_available()
    ai_status = ProviderHealthManager.get_status()
    queue_status = _check_redis_queue_status()
    is_ready = db_ok and (ai_status.get("is_live") or ai_status.get("is_testing"))
    status_code = 200 if is_ready else (503 if not db_ok else 200)

    return jsonify({
        "success": is_ready,
        "message": "Dependencies ready" if is_ready else "Dependencies degraded",
        "data": {
            "database": "ready" if db_ok else "unreachable",
            "llm_engine": f"{ai_status['provider']} ({ai_status['model']})" if ai_status.get("is_live") else ("testing" if ai_status.get("is_testing") else "not configured"),
            "redis": queue_status,
            "ai_status": ai_status.get("ai_status"),
            "provider": ai_status.get("provider"),
            "model": ai_status.get("model"),
            "service": SERVICE_NAME,
        },
        "error": None if db_ok else {"code": "DEPENDENCY_UNAVAILABLE", "message": "Database is unreachable"},
    }), status_code

