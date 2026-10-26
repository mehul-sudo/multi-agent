"""
Queue Architecture and Validation Utilities.

Restricts job queue submission to explicit, authorized queue names.
"""

from typing import Set

ALLOWED_QUEUES: Set[str] = {
    "default",
    "high_priority",
    "llm",
    "integrations",
    "maintenance",
    "recovery",
}


def validate_queue_name(queue_name: str) -> str:
    """Validate that the requested queue is in the authorized queue registry.

    Args:
        queue_name: Raw string name of requested queue.

    Returns:
        Sanitized queue name string.

    Raises:
        ValueError: If requested queue name is unauthorized or malformed.
    """
    if not queue_name:
        return "default"

    cleaned = queue_name.strip().lower()
    if cleaned not in ALLOWED_QUEUES:
        raise ValueError(
            f"Queue '{queue_name}' is not authorized. Allowed queues: {sorted(list(ALLOWED_QUEUES))}."
        )

    return cleaned
