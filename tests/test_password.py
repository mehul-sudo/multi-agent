"""Tests for app/security/password.py - independent of Flask/DB."""

import pytest

from app.security.password import (
    InvalidPasswordError,
    hash_password,
    verify_password,
)


def test_hash_password_produces_non_plaintext_hash():
    hashed = hash_password("correct-horse-battery")
    assert hashed != "correct-horse-battery"
    assert len(hashed) > 20


def test_verify_password_succeeds_for_correct_password():
    hashed = hash_password("correct-horse-battery")
    assert verify_password("correct-horse-battery", hashed) is True


def test_verify_password_fails_for_wrong_password():
    hashed = hash_password("correct-horse-battery")
    assert verify_password("wrong-password", hashed) is False


def test_hash_password_rejects_none():
    with pytest.raises(InvalidPasswordError):
        hash_password(None)


def test_hash_password_rejects_empty_string():
    with pytest.raises(InvalidPasswordError):
        hash_password("")


def test_hash_password_rejects_too_short_password():
    with pytest.raises(InvalidPasswordError):
        hash_password("short")


def test_verify_password_returns_false_for_empty_inputs():
    assert verify_password("", "somehash") is False
    assert verify_password("something", "") is False
    assert verify_password(None, None) is False
