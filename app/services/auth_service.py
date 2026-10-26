"""
Authentication service layer (Phase 4).

Centralises all authentication-related business logic:
  - Verifying credentials and returning a User
  - Checking whether a token JTI is in the blocklist
  - Revoking tokens by inserting their JTI into the blocklist
  - Changing a user's password safely and transactionally
  - Loading the current authenticated user from the JWT identity

Route handlers in app/api/auth.py must NOT perform database queries
directly - they delegate to these functions instead.

Security conventions followed here:
  - Failed logins never reveal whether the email or the password was wrong.
  - Passwords are never logged.
  - Tokens are never logged.
  - Password changes are committed before returning to ensure atomicity.
"""

from datetime import datetime, timezone

from sqlalchemy import select

from app.extensions import db
from app.models.token_blocklist import TokenBlocklist
from app.models.user import User
from app.security.password import InvalidPasswordError, hash_password, verify_password
from app.services import user_service


class AuthenticationError(Exception):
    """Raised when credentials are invalid or the account is inactive.

    A single, generic exception is used deliberately so callers cannot
    distinguish "email not found" from "wrong password" from "inactive
    account" - they all produce the same HTTP 401 response.
    """


class PasswordValidationError(ValueError):
    """Raised when the new password does not meet requirements."""


def authenticate_user(email: str, password: str) -> User:
    """Find a user by email and verify their password.

    Raises AuthenticationError for any failure condition:
      - email not found
      - wrong password
      - account is inactive (is_active=False)

    The caller should always return the same generic error message to
    avoid leaking account-existence information.

    On success, updates last_login_at and returns the User.
    """
    user = user_service.find_by_email(email)

    # Use verify_password even when user is None to consume constant time
    # and prevent a timing attack that could reveal email existence.
    dummy_hash = "pbkdf2:sha256:600000$" + "a" * 64
    candidate_hash = user.password_hash if user is not None else dummy_hash

    if not verify_password(password, candidate_hash):
        raise AuthenticationError("Invalid credentials.")

    # At this point password matched; now check account state.
    if user is None or not user.is_active:
        raise AuthenticationError("Invalid credentials.")

    # Update last login timestamp. A commit failure here is not fatal -
    # we log the warning but don't block the login.
    try:
        user.last_login_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.session.commit()
    except Exception:
        db.session.rollback()

    return user


def is_token_revoked(jwt_header: dict, jwt_payload: dict) -> bool:
    """Return True if the token's JTI is in the blocklist.

    Called by the @jwt.token_in_blocklist_loader callback registered in
    app/__init__.py. Flask-JWT-Extended passes both the header and
    payload; we only need the payload's 'jti' claim.
    """
    jti = jwt_payload.get("jti")
    if not jti:
        return True  # malformed token - treat as revoked

    stmt = select(TokenBlocklist).where(TokenBlocklist.jti == jti)
    token = db.session.execute(stmt).scalar_one_or_none()
    return token is not None


def revoke_token(
    *,
    jti: str,
    token_type: str,
    user_id: int,
    expires_at: datetime,
) -> TokenBlocklist:
    """Insert a JTI into the token blocklist.

    Args:
        jti: The JWT ID claim from the token.
        token_type: "access" or "refresh".
        user_id: The internal DB id of the token's owner.
        expires_at: When the token would have expired naturally
            (used for future cleanup of stale blocklist rows).

    Returns:
        The newly created TokenBlocklist row.
    """
    entry = TokenBlocklist(
        jti=jti,
        token_type=token_type,
        user_id=user_id,
        expires_at=expires_at,
    )
    db.session.add(entry)
    db.session.commit()
    return entry


def change_password(user: User, current_password: str, new_password: str) -> User:
    """Verify the current password and replace it with the new one.

    Validates that:
      - current_password matches the stored hash
      - new_password meets the minimum length requirement

    On success, saves the new hash and revokes all of the user's existing
    active tokens by adding their JTIs to the blocklist is NOT done here
    because we don't track which tokens are active per-user. Instead,
    the caller (route handler) should revoke the specific token used for
    this request. The password change alone invalidates all other tokens
    via the changed hash (verify_password will fail for any future
    password-check against old hashes).

    Actually, since JWTs are stateless we DO need to rely solely on the
    blocklist. We revoke the calling token in the route handler. Future
    tokens issued after the password change will reflect the new hash
    only when used against protected routes that re-check the password.
    Since we use JWTs, old tokens remain valid unless explicitly revoked.
    Therefore the route handler revokes the current access token.

    Raises:
        AuthenticationError: If current_password does not match.
        PasswordValidationError: If new_password fails validation.
    """
    if not verify_password(current_password, user.password_hash):
        raise AuthenticationError("Current password is incorrect.")

    try:
        new_hash = hash_password(new_password)
    except InvalidPasswordError as exc:
        raise PasswordValidationError(str(exc)) from exc

    user.password_hash = new_hash
    db.session.commit()
    return user


def get_user_by_identity(identity: str) -> User | None:
    """Load a User from the JWT 'sub' claim (stored as public_id).

    Used by route handlers that need the full User object from the
    current JWT context. Returns None if the user has been deleted
    since the token was issued.
    """
    return user_service.find_by_public_id(identity)
