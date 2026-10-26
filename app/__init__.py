"""
Application factory for the Multi-Agent AI Assistant backend.

This phase wires up:
  - configuration loading (development / testing / production)
  - JSON response settings
  - the SQLAlchemy extension (database connection)
  - Flask-Migrate (schema migrations)
  - Flask-JWT-Extended (JWT authentication - Phase 4)
  - the health-check blueprint (basic + database connectivity)
  - the users blueprint (user management)
  - the auth blueprint (login, refresh, logout, me, change-password)
"""

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

from flask import Flask

from app.config import get_config
from app.extensions import db, jwt, migrate, register_jwt_callbacks


def create_app(env_name: str | None = None, overrides: dict | None = None) -> Flask:
    """Create and configure a Flask application instance.

    Args:
        env_name: Optional explicit environment name
            ("development", "testing", "production"). When omitted,
            falls back to the FLASK_ENV environment variable.
        overrides: Optional dict of config values applied after the
            environment config is loaded but before extensions (e.g.
            SQLAlchemy) are initialized. Intended for tests that need
            to simulate a specific database configuration (such as an
            unreachable database) without mutating global environment
            state - extensions like SQLAlchemy bind to config values at
            init_app() time, so overriding config after create_app()
            has already run has no effect.

    Returns:
        A configured Flask application instance.

    Raises:
        RuntimeError: In production mode when JWT_SECRET_KEY or SECRET_KEY
            is missing (or SECRET_KEY is left at the insecure placeholder
            default), so the app never silently starts with a weak secret.
    """
    app = Flask(__name__)

    config_class = get_config(env_name)
    app.config.from_object(config_class)

    if overrides:
        app.config.update(overrides)

    # Guard: never allow production to start with weak/absent secrets.
    resolved_env = env_name or __import__("os").environ.get("FLASK_ENV", "development")
    if resolved_env == "production":
        if not app.config.get("JWT_SECRET_KEY"):
            raise RuntimeError(
                "JWT_SECRET_KEY must be set via environment variable in production. "
                "Generate a strong secret and export it before starting the server."
            )
        secret_key = app.config.get("SECRET_KEY")
        if not secret_key or secret_key == "change-this-value":
            raise RuntimeError(
                "SECRET_KEY must be set to a strong, unique value via environment "
                "variable in production. The built-in placeholder default is refused "
                "so the app never signs sessions with a publicly known key."
            )

    # Ensure JSON responses are returned in insertion order and are
    # human-readable during development.
    app.config.setdefault("JSON_SORT_KEYS", False)

    _register_extensions(app)
    _register_blueprints(app)

    try:
        with app.app_context():
            db.create_all()
    except Exception:
        pass

    # ── AI Provider Startup Configuration Validation ──
    from app.services.provider_health_service import ProviderHealthManager
    ProviderHealthManager.validate_startup_configuration(
        fail_fast=(resolved_env != "testing" and not ProviderHealthManager.is_testing_environment())
    )

    # Security middleware: Correlation ID, Rate Limiting, and Security Headers
    import uuid
    from flask import request, jsonify

    @app.before_request
    def security_before_request():
        correlation_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
        setattr(request, "correlation_id", correlation_id)

        # Rate Limit Check for login endpoint
        if request.endpoint and "login" in request.endpoint:
            from app.services.rate_limit_service import RateLimitService
            ip_key = f"ip:{request.remote_addr or '127.0.0.1'}"
            allowed, remaining, reset_after = RateLimitService.check_rate_limit(
                key=ip_key, endpoint_category="auth_login"
            )
            if not allowed:
                response = jsonify({
                    "error": "Too Many Requests",
                    "message": f"Rate limit exceeded for login attempts. Retry after {reset_after} seconds.",
                })
                response.status_code = 429
                response.headers["Retry-After"] = str(reset_after)
                return response

    @app.after_request
    def security_after_request(response):
        # Attach Correlation ID header
        correlation_id = getattr(request, "correlation_id", None)
        if correlation_id:
            response.headers["X-Correlation-ID"] = correlation_id

        # Attach Enterprise Security Headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Content-Security-Policy"] = "default-src 'self'"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

    return app



def _register_extensions(app: Flask) -> None:
    """Bind extension instances (defined in app/extensions.py) to this
    app instance. Extensions are defined once at module import time and
    initialized here to avoid circular imports between this module,
    models, and blueprints.
    """
    db.init_app(app)

    # Initialize Celery with app config
    from app.celery_app import init_celery
    init_celery(app)

    # Models must be imported (even if unused directly here) so that
    # Flask-Migrate's autogeneration can discover all tables.
    from app import models  # noqa: F401

    migrate.init_app(app, db)

    jwt.init_app(app)
    register_jwt_callbacks(jwt)

    # Wire up the token blocklist check so revoked tokens are rejected.
    from app.services.auth_service import is_token_revoked as _is_token_revoked

    @jwt.token_in_blocklist_loader
    def check_if_token_revoked(jwt_header, jwt_payload):
        return _is_token_revoked(jwt_header, jwt_payload)


def _register_blueprints(app: Flask) -> None:
    """Register all API blueprints under a common /api prefix."""
    from app.api.health import health_bp
    from app.api.users import users_bp
    from app.api.auth import auth_bp
    from app.api.agents import agents_bp
    from app.api.workflows import workflows_bp
    from app.api.executions import executions_bp
    from app.api.v1 import api_v1_bp

    app.register_blueprint(health_bp, url_prefix="/api")
    app.register_blueprint(users_bp, url_prefix="/api/users")
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(agents_bp, url_prefix="/api/agents")
    app.register_blueprint(workflows_bp, url_prefix="/api/workflows")
    app.register_blueprint(executions_bp, url_prefix="/api")
    app.register_blueprint(api_v1_bp, url_prefix="/api/v1")

