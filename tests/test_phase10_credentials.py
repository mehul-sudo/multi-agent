"""
Tests for Phase 10 Credential Vault (Fernet AES-256) and Secret Protection.
"""

import pytest
from app.services.credential_service import CredentialService


def test_credential_encryption_and_retrieval(db_session, user_factory):
    user = user_factory()
    secret_text = "super-secret-api-key-998877"

    cred = CredentialService.store_credential(
        name="Stripe API Key",
        secret_value=secret_text,
        owner_user_id=user.id,
        credential_type="api_key",
    )

    assert cred.public_id is not None
    # Secret plaintext must NOT be stored in the database column
    assert cred.encrypted_value != secret_text
    assert "super-secret" not in cred.encrypted_value

    # Internal service decryption returns the plaintext
    decrypted = CredentialService.get_credential_secret(cred.public_id, user.id)
    assert decrypted == secret_text


def test_credential_metadata_list_never_includes_plaintext(db_session, user_factory):
    user = user_factory()
    CredentialService.store_credential(
        name="AWS Secret Key",
        secret_value="AKIAIOSFODNN7EXAMPLE",
        owner_user_id=user.id,
    )

    metadata_list = CredentialService.list_credentials_metadata(owner_user_id=user.id)
    assert len(metadata_list) == 1
    assert "secret_value" not in metadata_list[0]
    assert "encrypted_value" not in metadata_list[0]
    assert metadata_list[0]["name"] == "AWS Secret Key"


def test_unauthorized_credential_access_rejected(db_session, user_factory):
    user1 = user_factory()
    user2 = user_factory()

    cred = CredentialService.store_credential(
        name="Private Key",
        secret_value="private-key-payload",
        owner_user_id=user1.id,
    )

    with pytest.raises(ValueError, match="Unauthorized"):
        CredentialService.get_credential_secret(cred.public_id, requesting_user_id=user2.id)
