"""
Password hashing utility.

Independent from any future JWT/session authentication logic - this
module only knows how to turn a plaintext password into a safe hash
and how to verify one. Nothing here issues tokens or manages sessions.

Uses Werkzeug's security helpers (already a transitive dependency of
Flask, well-maintained, salted pbkdf2 by default) rather than pulling
in a second hashing library.
"""

from werkzeug.security import check_password_hash, generate_password_hash

MIN_PASSWORD_LENGTH = 8


class InvalidPasswordError(ValueError):
    """Raised when a plaintext password fails basic validation.

    Deliberately does not include the offending password value in its
    message, so it is always safe to log/print this exception.
    """


def _validate_plaintext_password(password) -> str:
    if password is None:
        raise InvalidPasswordError("Password must not be None.")
    if not isinstance(password, str):
        raise InvalidPasswordError("Password must be a string.")
    if password == "":
        raise InvalidPasswordError("Password must not be empty.")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise InvalidPasswordError(
            f"Password must be at least {MIN_PASSWORD_LENGTH} characters long."
        )
    return password


def hash_password(password: str) -> str:
    """Hash a plaintext password for storage.

    Raises InvalidPasswordError for None, empty, non-string, or
    too-short passwords. Never logs the plaintext value.
    """
    validated = _validate_plaintext_password(password)
    return generate_password_hash(validated)


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a plaintext password against a stored hash.

    Returns False (rather than raising) for None/empty input or a
    missing hash, so callers can use this directly in a login check
    without extra branching. Never logs the plaintext value.
    """
    if not password or not password_hash:
        return False
    try:
        return check_password_hash(password_hash, password)
    except Exception:
        # A malformed hash should be treated as "does not match", not
        # crash the request.
        return False
