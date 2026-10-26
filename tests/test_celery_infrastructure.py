"""
Tests for Celery infrastructure, Flask context binding, configuration, and eager execution settings.
"""

import pytest
from app import create_app
from app.celery_app import celery, init_celery


def test_celery_app_initialization(app):
    """Verify Celery app instance is properly bound with Flask configuration."""
    assert celery is not None
    assert app.config["CELERY_TIMEZONE"] == "UTC"
    assert app.config["CELERY_ENABLE_UTC"] is True
    assert app.config["CELERY_TASK_SERIALIZER"] == "json"


def test_testing_config_uses_eager_execution(app):
    """In testing mode, CELERY_TASK_ALWAYS_EAGER must default to True."""
    assert app.config["CELERY_TASK_ALWAYS_EAGER"] is True
    assert app.config["CELERY_TASK_EAGER_PROPAGATES"] is True


def test_flask_context_task_execution(app):
    """Verify that tasks running through Celery execute within Flask application context."""
    with app.app_context():
        @celery.task(name="tests.test_context_task")
        def dummy_task():
            from flask import current_app
            return current_app.config["SECRET_KEY"]

        res = dummy_task.apply()
        assert res.get() == app.config["SECRET_KEY"]
