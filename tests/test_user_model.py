"""Tests for the User model and user_service repository layer."""

import pytest
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models.user import User
from app.security.password import hash_password, verify_password
from app.services import user_service


def _make_user(app, username="alice", email="alice@example.com", password="s3curePass!"):
    with app.app_context():
        user = user_service.create_user(
            username=username, email=email, password=password
        )
        return user.public_id


def test_user_can_be_created(app):
    with app.app_context():
        user = User(
            username="bob",
            email="bob@example.com",
            password_hash=hash_password("s3curePass!"),
        )
        db.session.add(user)
        db.session.commit()

        assert user.id is not None
        assert user.role == "user"
        assert user.is_active is True
        assert user.is_verified is False


def test_user_public_id_is_generated(app):
    with app.app_context():
        user = User(
            username="carol",
            email="carol@example.com",
            password_hash=hash_password("s3curePass!"),
        )
        db.session.add(user)
        db.session.commit()

        assert user.public_id is not None
        assert len(user.public_id) == 36  # UUID4 string length


def test_username_uniqueness_enforced(app):
    with app.app_context():
        db.session.add(
            User(
                username="dave",
                email="dave1@example.com",
                password_hash=hash_password("s3curePass!"),
            )
        )
        db.session.commit()

        db.session.add(
            User(
                username="dave",
                email="dave2@example.com",
                password_hash=hash_password("s3curePass!"),
            )
        )
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_email_uniqueness_enforced(app):
    with app.app_context():
        db.session.add(
            User(
                username="erin1",
                email="erin@example.com",
                password_hash=hash_password("s3curePass!"),
            )
        )
        db.session.commit()

        db.session.add(
            User(
                username="erin2",
                email="erin@example.com",
                password_hash=hash_password("s3curePass!"),
            )
        )
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_email_normalization_via_service(app):
    with app.app_context():
        user = user_service.create_user(
            username="frank",
            email="FRANK@Example.COM",
            password="s3curePass!",
        )
        assert user.email == "frank@example.com"


def test_password_is_hashed_not_plaintext(app):
    with app.app_context():
        user = user_service.create_user(
            username="grace",
            email="grace@example.com",
            password="s3curePass!",
        )
        assert user.password_hash != "s3curePass!"


def test_password_verification_succeeds_and_fails_correctly(app):
    with app.app_context():
        user = user_service.create_user(
            username="heidi",
            email="heidi@example.com",
            password="s3curePass!",
        )
        assert verify_password("s3curePass!", user.password_hash) is True
        assert verify_password("wrong-password", user.password_hash) is False


def test_create_user_raises_on_duplicate_username(app):
    with app.app_context():
        user_service.create_user(
            username="ivan", email="ivan1@example.com", password="s3curePass!"
        )
        with pytest.raises(user_service.DuplicateUsernameError):
            user_service.create_user(
                username="ivan", email="ivan2@example.com", password="s3curePass!"
            )


def test_create_user_raises_on_duplicate_email(app):
    with app.app_context():
        user_service.create_user(
            username="judy1", email="judy@example.com", password="s3curePass!"
        )
        with pytest.raises(user_service.DuplicateEmailError):
            user_service.create_user(
                username="judy2", email="judy@example.com", password="s3curePass!"
            )


def test_list_users_pagination(app):
    with app.app_context():
        for i in range(5):
            user_service.create_user(
                username=f"user{i}",
                email=f"user{i}@example.com",
                password="s3curePass!",
            )

        page1 = user_service.list_users(page=1, per_page=2)
        assert len(page1.users) == 2
        assert page1.total == 5
        assert page1.pages == 3

        page3 = user_service.list_users(page=3, per_page=2)
        assert len(page3.users) == 1


def test_update_profile_changes_only_safe_fields(app):
    with app.app_context():
        user = user_service.create_user(
            username="mallory", email="mallory@example.com", password="s3curePass!"
        )
        original_role = user.role
        original_hash = user.password_hash

        updated = user_service.update_profile(
            user, first_name="Mallory", last_name="M."
        )

        assert updated.first_name == "Mallory"
        assert updated.last_name == "M."
        assert updated.role == original_role
        assert updated.password_hash == original_hash


def test_deactivate_user_sets_is_active_false_but_keeps_record(app):
    with app.app_context():
        user = user_service.create_user(
            username="oscar", email="oscar@example.com", password="s3curePass!"
        )
        public_id = user.public_id

        user_service.deactivate_user(user)

        still_there = user_service.find_by_public_id(public_id)
        assert still_there is not None
        assert still_there.is_active is False
