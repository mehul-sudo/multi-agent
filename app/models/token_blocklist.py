"""
Token blocklist model (Phase 4 - JWT authentication).

When a user logs out or changes their password, the affected token's
JTI (JWT ID) is stored here. Every protected request checks this table
to reject revoked tokens. This turns the otherwise stateless JWT into
a safely revocable credential.

Design choices:
- expires_at is stored so old rows can be purged once they are past their
  natural expiry (no security value in keeping them forever).
- token_type is stored for auditability; the application currently
  checks all token types equally via the JWT_BLACKLIST_TOKEN_CHECKS config.
- The FK to users.id allows cascade cleanup and audit queries.
"""

from datetime import datetime, timezone

from app.extensions import db


def _utcnow() -> datetime:
    """Return a naive UTC datetime for storage.

    Matches the convention used by the User model so timestamps are
    consistently naive-UTC throughout the project.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


class TokenBlocklist(db.Model):
    """A revoked JWT.

    A token whose JTI appears in this table will be rejected by
    @jwt_required() even if it has not yet expired according to its
    embedded exp claim.
    """

    __tablename__ = "token_blocklist"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # JWT ID (jti claim) - the unique identifier for a specific token.
    # Indexed for fast lookup on every authenticated request.
    jti = db.Column(db.String(36), unique=True, index=True, nullable=False)

    # "access" or "refresh"
    token_type = db.Column(db.String(16), nullable=False)

    # FK to the user who owned this token - for audit / cascade queries.
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # When the row was inserted (i.e., when the token was revoked).
    revoked_at = db.Column(db.DateTime, nullable=False, default=_utcnow)

    # When the token itself would have expired naturally.
    # Rows where expires_at < now() can be safely purged without
    # affecting security - the token is already expired by JWT rules.
    expires_at = db.Column(db.DateTime, nullable=False)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid only
        return f"<TokenBlocklist jti={self.jti!r} type={self.token_type!r}>"
