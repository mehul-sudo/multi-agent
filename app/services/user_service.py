"""
User repository / service layer.

All database access for users goes through this module - route
handlers in app/api/users.py must not query or mutate the User model
directly. This keeps database logic testable in isolation and keeps
route files focused on request/response handling only.

Only "safe" profile fields (first_name, last_name, username) can be
changed via update_profile(). Role, password hash, is_active, and
is_verified are intentionally not settable here - they will be
handled by dedicated administrative/authentication workflows in a
later phase.
"""

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models.user import User
from app.security.password import hash_password

DEFAULT_PER_PAGE = 20
MAX_PER_PAGE = 100


class DuplicateUsernameError(Exception):
    """Raised when a username is already taken."""


class DuplicateEmailError(Exception):
    """Raised when an email is already registered."""


@dataclass
class PaginatedUsers:
    users: list[User]
    page: int
    per_page: int
    total: int
    pages: int


def username_exists(username: str) -> bool:
    stmt = select(func.count()).select_from(User).where(User.username == username)
    return db.session.execute(stmt).scalar_one() > 0


def email_exists(email: str) -> bool:
    normalized = email.lower()
    stmt = select(func.count()).select_from(User).where(User.email == normalized)
    return db.session.execute(stmt).scalar_one() > 0


def find_by_id(user_id: int) -> User | None:
    return db.session.get(User, user_id)


def find_by_public_id(public_id: str) -> User | None:
    stmt = select(User).where(User.public_id == public_id)
    return db.session.execute(stmt).scalar_one_or_none()


def find_by_username(username: str) -> User | None:
    stmt = select(User).where(User.username == username)
    return db.session.execute(stmt).scalar_one_or_none()


def find_by_email(email: str) -> User | None:
    stmt = select(User).where(User.email == email.lower())
    return db.session.execute(stmt).scalar_one_or_none()


def create_user(
    *,
    username: str,
    email: str,
    password: str,
    first_name: str | None = None,
    last_name: str | None = None,
) -> User:
    """Create a new user with the default role/active/verified state.

    Raises DuplicateUsernameError / DuplicateEmailError on conflicts
    (checked up front, and also guarded against a race condition via
    the underlying unique DB constraints + IntegrityError handling).
    """
    normalized_email = email.lower()

    if username_exists(username):
        raise DuplicateUsernameError(f"Username '{username}' is already taken.")
    if email_exists(normalized_email):
        raise DuplicateEmailError("A user with this email already exists.")

    user = User(
        username=username,
        email=normalized_email,
        password_hash=hash_password(password),
        first_name=first_name,
        last_name=last_name,
    )

    db.session.add(user)
    try:
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        # Fall back to a race-condition-safe check to report the right
        # conflict, since the up-front checks above cannot fully
        # prevent a concurrent insert between check and commit.
        if username_exists(username):
            raise DuplicateUsernameError(
                f"Username '{username}' is already taken."
            ) from exc
        if email_exists(normalized_email):
            raise DuplicateEmailError(
                "A user with this email already exists."
            ) from exc
        raise

    # Auto-seed the 8 enterprise agents for every new user account
    try:
        from app.services.agent_service import create_agent
        _default_agents = [
            ("Executive Email Agent", "email", "Drafts and sends executive notifications and alerts."),
            ("Market & Data Analysis Agent", "data_analysis", "Calculates statistics, metrics, and anomaly insights."),
            ("Executive Report Publisher", "report_generation", "Compiles multi-source intelligence into PDF/Markdown reports."),
            ("Enterprise Webhook / HTTP Agent", "http_webhook", "Dispatches REST payloads and triggers third-party webhooks."),
            ("Security & Vulnerability Scanner", "security_analysis", "Audits tokens, OWASP vulnerabilities, and data leakage."),
            ("SQL & Business Intelligence Agent", "database_bi", "Executes read-only analytical queries against corporate data stores."),
            ("Document Research & Synthesis Agent", "document_research", "Synthesizes documents, PDFs, and web findings into dossiers."),
        ]
        for name, a_type, instructions in _default_agents:
            create_agent(user.id, {
                "name": name,
                "agent_type": a_type,
                "system_instructions": instructions,
                "provider": "mock",
                "model": f"mock-{a_type}-v1",
            })
    except Exception:
        pass

    return user


def update_profile(
    user: User,
    *,
    username: str | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
) -> User:
    """Update only safe profile fields on an existing user.

    Any field left as None is left unchanged. This function never
    touches role, password_hash, is_active, or is_verified.
    """
    if username is not None and username != user.username:
        if username_exists(username):
            raise DuplicateUsernameError(f"Username '{username}' is already taken.")
        user.username = username

    if first_name is not None:
        user.first_name = first_name

    if last_name is not None:
        user.last_name = last_name

    try:
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        raise DuplicateUsernameError(
            f"Username '{username}' is already taken."
        ) from exc

    return user


def deactivate_user(user: User) -> User:
    """Soft-deactivate a user: set is_active=False, keep the record."""
    user.is_active = False
    db.session.commit()
    return user


def list_users(page: int = 1, per_page: int = DEFAULT_PER_PAGE) -> PaginatedUsers:
    """List users with safe, bounded pagination."""
    page = max(page, 1)
    per_page = max(1, min(per_page, MAX_PER_PAGE))

    total_stmt = select(func.count()).select_from(User)
    total = db.session.execute(total_stmt).scalar_one()

    pages = (total + per_page - 1) // per_page if total else 0

    stmt = (
        select(User)
        .order_by(User.id.asc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    users = list(db.session.execute(stmt).scalars().all())

    return PaginatedUsers(
        users=users, page=page, per_page=per_page, total=total, pages=pages
    )
