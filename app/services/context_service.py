"""
ContextService.

Scoped agent memory management (`GLOBAL`, `PLAN`, `TASK`, `AGENT_PRIVATE`).
Handles optimistic locking, context versioning, size limits, and secret/PII redaction.

Optimistic Locking
------------------
``set_context_entry`` accepts an optional ``expected_version`` argument.  When
provided, the function performs a compare-and-swap (CAS) check: if the record's
current version does not match ``expected_version``, a
``ContextVersionConflictError`` is raised immediately and no data is written.
This prevents silent overwrites when two concurrent callers both read the same
version and then both attempt to update it.

When ``expected_version`` is *not* provided the function performs an
unconditional update, preserving full backward compatibility with all existing
call sites that do not need CAS semantics.
"""

from typing import Any, Dict, List, Optional

from app.extensions import db
from app.models.shared_context import (
    CONTEXT_SCOPE_AGENT_PRIVATE,
    CONTEXT_SCOPE_GLOBAL,
    CONTEXT_SCOPE_PLAN,
    CONTEXT_SCOPE_TASK,
    ContextVersion,
    SharedContextRecord,
)
from app.services.secret_service import redact_secrets

MAX_CONTEXT_KEY_BYTES = 256
MAX_CONTEXT_VALUE_BYTES = 524288  # 512 KB limit per entry


class ContextSizeExceededError(ValueError):
    """Raised when context key/value exceeds safe payload size limits."""
    pass


class ContextAccessDeniedError(PermissionError):
    """Raised when an agent attempts to access private context belonging to another agent."""
    pass


class ContextVersionConflictError(ValueError):
    """Raised when an optimistic-locking version check fails.

    The caller read a record at version *expected*, but by the time the
    update was attempted another writer had already advanced the version.
    The caller must re-read the current version before retrying.

    Attributes
    ----------
    expected_version : int
        The version the caller believed the record was at.
    actual_version : int
        The version the record was actually at when the update was attempted.
    """

    def __init__(self, key: str, expected_version: int, actual_version: int) -> None:
        self.expected_version = expected_version
        self.actual_version = actual_version
        super().__init__(
            f"Optimistic locking conflict for context key '{key}': "
            f"expected version {expected_version} but found version {actual_version}. "
            "Re-read the record and retry your update."
        )


def set_context_entry(
    orchestration_id: int,
    key: str,
    value: Any,
    scope: str = CONTEXT_SCOPE_GLOBAL,
    plan_id: Optional[int] = None,
    task_id: Optional[int] = None,
    agent_id: Optional[int] = None,
    is_sensitive: bool = False,
    expected_version: Optional[int] = None,
) -> SharedContextRecord:
    """Set or update a scoped context entry with version tracking.

    Parameters
    ----------
    orchestration_id : int
        Orchestration session the entry belongs to.
    key : str
        The context key to set.
    value : Any
        The value to store (must be JSON-serialisable).
    scope : str
        One of CONTEXT_SCOPE_GLOBAL, CONTEXT_SCOPE_PLAN, CONTEXT_SCOPE_TASK,
        CONTEXT_SCOPE_AGENT_PRIVATE.
    plan_id, task_id, agent_id : Optional[int]
        Scope qualifiers used when scope is PLAN, TASK, or AGENT_PRIVATE.
    is_sensitive : bool
        When True, the raw value is stored without secret-redaction (caller
        is responsible for providing already-redacted data if needed).
    expected_version : Optional[int]
        When provided, a compare-and-swap (CAS) check is performed: if the
        record's current ``version`` does not equal *expected_version*, a
        ``ContextVersionConflictError`` is raised and no data is written.
        Pass ``None`` (the default) to perform an unconditional update,
        which preserves backward compatibility with existing call sites.

    Returns
    -------
    SharedContextRecord
        The created or updated record.

    Raises
    ------
    ContextSizeExceededError
        When *value* serialises to more bytes than MAX_CONTEXT_VALUE_BYTES.
    ContextVersionConflictError
        When *expected_version* is provided and does not match the record's
        current version (optimistic locking conflict).
    """
    import json

    serialized_val = json.dumps(value)
    if len(serialized_val) > MAX_CONTEXT_VALUE_BYTES:
        raise ContextSizeExceededError(
            f"Context entry value for key '{key}' exceeds maximum limit of {MAX_CONTEXT_VALUE_BYTES} bytes."
        )

    clean_value = redact_secrets(value) if not is_sensitive else value

    query = SharedContextRecord.query.filter_by(
        orchestration_id=orchestration_id,
        scope=scope,
        key=key,
    )
    if scope == CONTEXT_SCOPE_AGENT_PRIVATE and agent_id:
        query = query.filter_by(agent_id=agent_id)

    record = query.first()

    if record:
        # --- Optimistic locking: compare-and-swap check ---
        # When the caller provides expected_version, we must verify that the
        # record has not been concurrently modified since the caller last read
        # it.  If the versions differ we raise immediately and write nothing,
        # ensuring no silent data loss from concurrent updates.
        if expected_version is not None and record.version != expected_version:
            raise ContextVersionConflictError(
                key=key,
                expected_version=expected_version,
                actual_version=record.version,
            )
        record.value = clean_value
        record.version += 1
        record.is_sensitive = is_sensitive

    else:
        record = SharedContextRecord(
            orchestration_id=orchestration_id,
            plan_id=plan_id,
            task_id=task_id,
            agent_id=agent_id,
            scope=scope,
            key=key,
            value=clean_value,
            is_sensitive=is_sensitive,
            version=1,
        )
        db.session.add(record)

    db.session.flush()

    # Create historical version snapshot
    version_snapshot = ContextVersion(
        context_record_id=record.id,
        version=record.version,
        value=clean_value,
        updated_by_agent_id=agent_id,
    )
    db.session.add(version_snapshot)
    db.session.commit()

    return record


def get_context_entry(
    orchestration_id: int,
    key: str,
    scope: str = CONTEXT_SCOPE_GLOBAL,
    requesting_agent_id: Optional[int] = None,
) -> Optional[Any]:
    """Retrieve a context value enforcing scope permissions."""
    query = SharedContextRecord.query.filter_by(
        orchestration_id=orchestration_id,
        scope=scope,
        key=key,
    )
    record = query.first()
    if not record:
        return None

    # Enforce agent-private boundary
    if record.scope == CONTEXT_SCOPE_AGENT_PRIVATE and record.agent_id != requesting_agent_id:
        raise ContextAccessDeniedError(f"Agent {requesting_agent_id} cannot access private context of Agent {record.agent_id}")

    return record.value


def get_all_context_for_orchestration(orchestration_id: int, requesting_agent_id: Optional[int] = None) -> Dict[str, Any]:
    """Retrieve all accessible context records for an orchestration session as a dict."""
    records = SharedContextRecord.query.filter_by(orchestration_id=orchestration_id).all()
    context_map = {}
    for r in records:
        if r.scope == CONTEXT_SCOPE_AGENT_PRIVATE and r.agent_id != requesting_agent_id:
            continue
        context_map[r.key] = r.value
    return context_map
