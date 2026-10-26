"""API blueprint package.

Each API sub-module (health.py, and future modules like auth.py,
agents.py, tasks.py, etc.) defines its own Blueprint. The app factory
imports and registers them explicitly, keeping registration order and
URL prefixes visible in one place (see app/__init__.py).
"""
