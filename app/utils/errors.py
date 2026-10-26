"""Shared error-response helper.

Produces a consistent JSON error shape across all API endpoints:

    {"error": {"code": "VALIDATION_ERROR", "message": "..."}}

Never include raw exception objects or stack traces here - only a
short machine-readable code and a human-readable message.
"""

from flask import jsonify


class ResourceNotFoundError(Exception):
    """Raised when a requested domain resource is missing or inaccessible."""
    pass


def error_response(code: str, message: str, status: int, details: list | None = None):
    """Build a (response, status_code) tuple with the standardized API error shape."""
    payload = {
        "success": False,
        "message": message,
        "data": None,
        "error": {
            "code": code,
            "message": message,
            "details": details if details is not None else [],
        },
    }
    return jsonify(payload), status


def success_response(data: dict | list | None = None, message: str = "Success", status: int = 200):
    """Build a (response, status_code) tuple with the standardized API success shape."""
    payload = {
        "success": True,
        "message": message,
        "data": data,
        "error": None,
    }
    return jsonify(payload), status

