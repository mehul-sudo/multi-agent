"""
Celery Worker Entrypoint.

Usage:
    celery -A celery_worker.celery worker --loglevel=INFO -Q default,high_priority,llm,integrations,maintenance,recovery
"""

from app import create_app
from app.celery_app import celery_app

app = create_app()
celery = celery_app
