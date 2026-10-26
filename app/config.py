"""
Application configuration.

Configuration is loaded from environment variables (see .env.example).
No secrets are hard-coded here. Each environment (development, testing,
production) gets its own config class so the app factory can select the
correct one at creation time.
"""

import os
from datetime import timedelta


class BaseConfig:
    """Shared defaults. Do not put real secrets here."""

    SECRET_KEY = os.environ.get("SECRET_KEY", "change-this-value")
    JSON_SORT_KEYS = False

    # Raw database URL as provided by the environment. May be empty -
    # each environment-specific config below decides what to fall back
    # to when it is missing, so the app can still start (e.g. for the
    # basic health check) without a running PostgreSQL instance.
    DATABASE_URL = os.environ.get("DATABASE_URL", "")

    # Flask-SQLAlchemy settings shared by all environments.
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # --- JWT Authentication (Phase 4) ---
    # JWT_SECRET_KEY must be set to a strong random value in non-dev
    # environments. Each subclass provides the appropriate default/guard.
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "")

    # Access tokens expire after JWT_ACCESS_TOKEN_EXPIRES_MINUTES minutes.
    # Refresh tokens expire after JWT_REFRESH_TOKEN_EXPIRES_DAYS days.
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(
        minutes=int(os.environ.get("JWT_ACCESS_TOKEN_EXPIRES_MINUTES", 15))
    )
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(
        days=int(os.environ.get("JWT_REFRESH_TOKEN_EXPIRES_DAYS", 30))
    )

    # Only accept tokens from HTTP Authorization header (Bearer scheme).
    JWT_TOKEN_LOCATION = ["headers"]

    # Enable blocklist checking for both access and refresh tokens.
    JWT_BLACKLIST_ENABLED = True
    JWT_BLACKLIST_TOKEN_CHECKS = ["access", "refresh"]

    # Placeholders for future phases (not used yet, but documented here
    # so the config surface is stable as the project grows).
    LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "")
    LLM_MODEL = os.environ.get("LLM_MODEL", "")
    LLM_API_KEY = os.environ.get("LLM_API_KEY", "")

    # --- Phase 7 Celery & Redis Distributed Engine Config ---
    CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
    CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")
    CELERY_TASK_ALWAYS_EAGER = os.environ.get("CELERY_TASK_ALWAYS_EAGER", "false").lower() in ("true", "1", "t")
    CELERY_TASK_EAGER_PROPAGATES = os.environ.get("CELERY_TASK_EAGER_PROPAGATES", "true").lower() in ("true", "1", "t")
    CELERY_TASK_SERIALIZER = os.environ.get("CELERY_TASK_SERIALIZER", "json")
    CELERY_RESULT_SERIALIZER = os.environ.get("CELERY_RESULT_SERIALIZER", "json")
    CELERY_ACCEPT_CONTENT = ["json"]
    CELERY_TIMEZONE = os.environ.get("CELERY_TIMEZONE", "UTC")
    CELERY_ENABLE_UTC = True
    CELERY_TASK_TRACK_STARTED = True
    CELERY_TASK_ACKS_LATE = True
    CELERY_WORKER_PREFETCH_MULTIPLIER = int(os.environ.get("CELERY_WORKER_PREFETCH_MULTIPLIER", "1"))
    CELERY_RESULT_EXPIRES = int(os.environ.get("CELERY_RESULT_EXPIRES", "86400"))

    # Phase 7 Limits and Thresholds
    MAX_USER_CONCURRENT_JOBS = int(os.environ.get("MAX_USER_CONCURRENT_JOBS", "10"))
    MAX_WORKFLOW_CONCURRENT_JOBS = int(os.environ.get("MAX_WORKFLOW_CONCURRENT_JOBS", "5"))
    STALE_JOB_THRESHOLD_SECONDS = int(os.environ.get("STALE_JOB_THRESHOLD_SECONDS", "300"))

    TESTING = False
    DEBUG = False

    @staticmethod
    def _pool_options() -> dict:
        """Reasonable connection pool defaults for a real (non-SQLite)
        database. SQLite in this project is only used for local
        development fallback and tests, where a connection pool is not
        meaningful, so these options are applied only when a real
        DATABASE_URL is configured (see subclasses).
        """
        return {
            "pool_size": int(os.environ.get("DB_POOL_SIZE", 5)),
            "max_overflow": int(os.environ.get("DB_MAX_OVERFLOW", 10)),
            "pool_timeout": int(os.environ.get("DB_POOL_TIMEOUT", 30)),
            "pool_pre_ping": True,
        }


class DevelopmentConfig(BaseConfig):
    DEBUG = True

    # Falls back to a local SQLite file if DATABASE_URL is not set, so
    # a developer can run the app immediately without PostgreSQL.
    SQLALCHEMY_DATABASE_URI = BaseConfig.DATABASE_URL or "sqlite:///dev.db"

    SQLALCHEMY_ENGINE_OPTIONS = (
        BaseConfig._pool_options() if BaseConfig.DATABASE_URL else {}
    )

    # Development JWT secret - acceptable for local use only.
    # Never use this value outside of development.
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "dev-jwt-secret-change-me")


class TestingConfig(BaseConfig):
    TESTING = True
    DEBUG = True
    SECRET_KEY = "testing-secret-key"

    # In-memory SQLite with StaticPool so all threads/tasks share the exact same connection and tables.
    from sqlalchemy.pool import StaticPool
    SQLALCHEMY_DATABASE_URI = os.environ.get("TEST_DATABASE_URL", "sqlite://")
    SQLALCHEMY_ENGINE_OPTIONS = {
        "connect_args": {"check_same_thread": False},
        "poolclass": StaticPool,
    }

    # Short-lived tokens for testing. The test suite can override via
    # create_app(overrides={...}) when specific expiry behavior is needed.
    JWT_SECRET_KEY = "testing-jwt-secret-key"
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=15)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)

    # In testing mode, default to eager execution unless overridden
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_TASK_EAGER_PROPAGATES = True



class ProductionConfig(BaseConfig):
    DEBUG = False

    # No SQLite fallback in production - DATABASE_URL must be a real
    # PostgreSQL URL. Left empty here if unset rather than raising, so
    # importing this module never fails; the database utility (see
    # app/services/db_health.py) reports connectivity issues at
    # request time instead of crashing the process at import time.
    SQLALCHEMY_DATABASE_URI = BaseConfig.DATABASE_URL
    SQLALCHEMY_ENGINE_OPTIONS = (
        BaseConfig._pool_options() if BaseConfig.DATABASE_URL else {}
    )

    # Production JWT secret MUST be set via environment variable.
    # The application factory raises at startup when it is missing so
    # the app never silently runs with an empty/weak secret.
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "")


CONFIG_MAP = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}


def get_config(env_name: str | None = None):
    """Return the config class for the given environment name.

    Falls back to FLASK_ENV (or 'development') when env_name is not given.
    """
    env_name = env_name or os.environ.get("FLASK_ENV", "development")
    return CONFIG_MAP.get(env_name, DevelopmentConfig)
