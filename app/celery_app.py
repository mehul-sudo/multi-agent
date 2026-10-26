"""
Celery Application Factory.

Integrates Celery distributed task execution with the Flask application factory.
Ensures task execution occurs within the Flask app context.
"""

from typing import Any, Optional
from celery import Celery
from flask import Flask

celery = Celery("multi_agent_backend")


def init_celery(app: Flask, celery_instance: Optional[Celery] = None) -> Celery:
    """Bind Flask application configuration and context to Celery instance."""
    instance = celery_instance or celery

    instance.conf.update(
        broker_url=app.config.get("CELERY_BROKER_URL", "redis://localhost:6379/0"),
        result_backend=app.config.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/0"),
        task_always_eager=app.config.get("CELERY_TASK_ALWAYS_EAGER", False),
        task_eager_propagates=app.config.get("CELERY_TASK_EAGER_PROPAGATES", True),
        task_serializer=app.config.get("CELERY_TASK_SERIALIZER", "json"),
        result_serializer=app.config.get("CELERY_RESULT_SERIALIZER", "json"),
        accept_content=app.config.get("CELERY_ACCEPT_CONTENT", ["json"]),
        timezone=app.config.get("CELERY_TIMEZONE", "UTC"),
        enable_utc=app.config.get("CELERY_ENABLE_UTC", True),
        task_track_started=app.config.get("CELERY_TASK_TRACK_STARTED", True),
        task_acks_late=app.config.get("CELERY_TASK_ACKS_LATE", True),
        worker_prefetch_multiplier=app.config.get("CELERY_WORKER_PREFETCH_MULTIPLIER", 1),
        result_expires=app.config.get("CELERY_RESULT_EXPIRES", 86400),
        # Ensure the worker imports task modules on startup so their
        # @celery_app.task definitions are registered. Import happens at
        # worker boot (not here), so this stays circular-import safe.
        imports=(
            "app.tasks.workflow_tasks",
            "app.tasks.orchestration_tasks",
        ),
    )

    class ContextTask(instance.Task):
        def __call__(self, *args: Any, **kwargs: Any) -> Any:
            from flask import current_app, has_app_context

            if has_app_context():
                return self.run(*args, **kwargs)

            ctx_app = getattr(instance, "flask_app", None)
            if ctx_app:
                with ctx_app.app_context():
                    return self.run(*args, **kwargs)

            return self.run(*args, **kwargs)

    instance.Task = ContextTask
    instance.flask_app = app
    return instance


# Alias for backward compatibility
celery_app = celery
