"""
Encrypted Credential model.

Stores API keys, passwords, access tokens, and webhook secrets securely
encrypted at rest using AES-256 Fernet encryption. Plaintext secrets are
never persisted in database columns, logs, or API responses.
"""

import uuid
from datetime import datetime, timezone

from app.extensions import db


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class EncryptedCredential(db.Model):
    """Credential vault entry with encrypted value at rest."""

    __tablename__ = "encrypted_credentials"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    public_id = db.Column(
        db.String(36),
        unique=True,
        index=True,
        nullable=False,
        default=lambda: str(uuid.uuid4()),
    )

    name = db.Column(db.String(128), nullable=False)
    credential_type = db.Column(db.String(64), nullable=False, default="api_key")
    description = db.Column(db.Text, nullable=True)

    # Encrypted value payload (ciphertext base64 encoded)
    encrypted_value = db.Column(db.Text, nullable=False)

    # Scoping
    organization_id = db.Column(
        db.Integer, db.ForeignKey("organizations.id"), nullable=True, index=True
    )
    owner_user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False, index=True
    )

    is_active = db.Column(db.Boolean, nullable=False, default=True)
    expires_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=_utcnow, onupdate=_utcnow
    )

    def __repr__(self) -> str:
        return f"<EncryptedCredential public_id={self.public_id} name={self.name!r}>"
