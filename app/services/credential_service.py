"""
Credential Vault Service.

Provides authenticated symmetric encryption at rest for sensitive secrets,
API keys, database passwords, OAuth tokens, and webhook secrets. Encryption
uses Fernet (AES-128 in CBC mode with an HMAC-SHA256 authentication tag),
so ciphertext is tamper-evident. Plaintext values are never logged, returned
via API endpoints, or exposed in audit trails.
"""

import os
import base64
from typing import Any, Dict, List, Optional, Tuple

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from app.extensions import db
from app.models.encrypted_credential import EncryptedCredential


class CredentialService:
    """Service for encrypting, storing, decrypting, and rotating credentials."""

    @classmethod
    def _get_fernet_cipher(cls) -> Fernet:
        """Obtain the Fernet cipher (AES-128-CBC + HMAC-SHA256) from configuration.

        In production a ``CREDENTIAL_ENCRYPTION_KEY`` MUST be provided via the
        environment; the service fails closed (RuntimeError) rather than
        silently encrypting real secrets with a well-known development key.
        Development and testing fall back to a deterministic key so the test
        suite can run without external configuration - that fallback key is
        NOT secret and must never protect real credentials.
        """
        raw_key = os.getenv("CREDENTIAL_ENCRYPTION_KEY")
        if not raw_key:
            env_name = os.getenv("FLASK_ENV", "development").lower()
            if env_name == "production":
                raise RuntimeError(
                    "CREDENTIAL_ENCRYPTION_KEY must be set via environment variable "
                    "in production. Refusing to encrypt credentials with a default "
                    "development key."
                )
            # Development/testing ONLY: deterministic, non-secret fallback key.
            secret = b"phase10-default-master-encryption-key-for-testing"
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=b"static_salt_phase10",
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(secret))
            return Fernet(key)

        # A key was explicitly provided. Accept a proper urlsafe-base64 Fernet
        # key directly; otherwise derive one deterministically from the
        # provided passphrase.
        try:
            return Fernet(raw_key.encode() if isinstance(raw_key, str) else raw_key)
        except Exception:
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=b"static_salt_phase10",
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(raw_key.encode()))
            return Fernet(key)

    @classmethod
    def store_credential(
        cls,
        name: str,
        secret_value: str,
        owner_user_id: int,
        credential_type: str = "api_key",
        description: Optional[str] = None,
        organization_id: Optional[int] = None,
        expires_at: Optional[Any] = None,
    ) -> EncryptedCredential:
        """Encrypt and persist a secret. Plaintext is never stored in DB."""
        if not secret_value:
            raise ValueError("Secret value cannot be empty")

        cipher = cls._get_fernet_cipher()
        encrypted_bytes = cipher.encrypt(secret_value.encode("utf-8"))
        encrypted_str = encrypted_bytes.decode("utf-8")

        credential = EncryptedCredential(
            name=name,
            credential_type=credential_type,
            description=description,
            encrypted_value=encrypted_str,
            owner_user_id=owner_user_id,
            organization_id=organization_id,
            expires_at=expires_at,
            is_active=True,
        )
        db.session.add(credential)
        db.session.commit()
        return credential

    @classmethod
    def get_credential_secret(cls, public_id: str, requesting_user_id: int) -> str:
        """Retrieve and decrypt plaintext secret for internal service execution only."""
        cred = EncryptedCredential.query.filter_by(public_id=public_id, is_active=True).first()
        if not cred:
            raise ValueError("Credential not found or revoked")

        # Ownership or org check
        if cred.owner_user_id != requesting_user_id:
            from app.services.organization_service import OrganizationService
            if not (cred.organization_id and OrganizationService.validate_tenant_access(requesting_user_id, cred.organization_id)):
                raise ValueError("Unauthorized to access credential secret")

        cipher = cls._get_fernet_cipher()
        decrypted_bytes = cipher.decrypt(cred.encrypted_value.encode("utf-8"))
        return decrypted_bytes.decode("utf-8")

    @classmethod
    def list_credentials_metadata(
        cls, owner_user_id: int, organization_id: Optional[int] = None
    ) -> List[Dict]:
        """List credentials metadata ONLY. Plaintext secrets are NEVER included.

        Security
        --------
        When *organization_id* is provided, the calling user must be an active
        member of that organization.  If they are not, a ``PermissionError`` is
        raised and no credential data is returned.  This prevents cross-
        organization IDOR where a user could enumerate another organization's
        credentials by supplying an arbitrary ``organization_id`` parameter.

        Parameters
        ----------
        owner_user_id : int
            The numeric ID of the calling user (set from ``current_user.id``
            in the API layer).
        organization_id : Optional[int]
            When supplied, only credentials scoped to this organization are
            returned.  The caller must be a member of this organization.

        Raises
        ------
        PermissionError
            When *organization_id* is provided and the calling user is not an
            active member of that organization.
        """
        if organization_id is not None:
            # --- IDOR Guard ---
            # Verify the calling user is an active member of the requested org
            # before returning any data.  Without this check, any authenticated
            # user could supply an arbitrary organization_id to enumerate
            # credentials belonging to a completely different organization.
            from app.models.organization import OrganizationMember
            membership = OrganizationMember.query.filter_by(
                organization_id=organization_id,
                user_id=owner_user_id,
                is_active=True,
            ).first()
            if membership is None:
                raise PermissionError(
                    f"User {owner_user_id} is not an authorized member of "
                    f"organization {organization_id} and cannot access its credentials."
                )
            query = EncryptedCredential.query.filter_by(
                is_active=True, organization_id=organization_id
            )
        else:
            query = EncryptedCredential.query.filter_by(
                is_active=True, owner_user_id=owner_user_id
            )

        credentials = query.all()
        return [
            {
                "public_id": c.public_id,
                "name": c.name,
                "credential_type": c.credential_type,
                "description": c.description,
                "organization_id": c.organization_id,
                "created_at": c.created_at.isoformat() if c.created_at else None,
                "updated_at": c.updated_at.isoformat() if c.updated_at else None,
            }
            for c in credentials
        ]


    @classmethod
    def revoke_credential(cls, public_id: str, owner_user_id: int) -> bool:
        """Revoke / soft-delete a credential."""
        cred = EncryptedCredential.query.filter_by(public_id=public_id, owner_user_id=owner_user_id).first()
        if not cred:
            return False

        cred.is_active = False
        db.session.commit()
        return True
