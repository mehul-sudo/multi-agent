import os
import sys

# Make sure `app` package is importable when pytest is run from the backend/ directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import pytest
from flask_jwt_extended import create_access_token

from app import create_app
from app.extensions import db
from app.models.user import User
from app.security.password import hash_password


@pytest.fixture
def app():
    """Create a Flask app configured for testing."""
    application = create_app(env_name="testing")

    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """Flask test client for making requests against the app."""
    return app.test_client()


@pytest.fixture
def db_session(app):
    """Database session fixture."""
    with app.app_context():
        yield db.session


@pytest.fixture
def test_user(app):
    """Create a default test user."""
    with app.app_context():
        user = User(
            username="testuser",
            email="testuser@example.com",
            password_hash=hash_password("Password123!"),
            is_active=True,
        )
        db.session.add(user)
        db.session.commit()
        user = User.query.get(user.id)
        return user


@pytest.fixture
def auth_headers(app, test_user):
    """Create Authorization headers for test_user."""
    with app.app_context():
        token = create_access_token(identity=test_user.public_id)
        return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def other_user(app):
    """Create a secondary user for cross-user tests."""
    with app.app_context():
        user = User(
            username="otheruser",
            email="otheruser@example.com",
            password_hash=hash_password("Password123!"),
            is_active=True,
        )
        db.session.add(user)
        db.session.commit()
        user = User.query.get(user.id)
        return user


@pytest.fixture
def other_auth_headers(app, other_user):
    """Create Authorization headers for other_user."""
    with app.app_context():
        token = create_access_token(identity=other_user.public_id)
        return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_user(app):
    """Create a user with the platform 'admin' role for authorization tests."""
    with app.app_context():
        user = User(
            username="adminuser",
            email="adminuser@example.com",
            password_hash=hash_password("Password123!"),
            role="admin",
            is_active=True,
        )
        db.session.add(user)
        db.session.commit()
        user = User.query.get(user.id)
        return user


@pytest.fixture
def admin_auth_headers(app, admin_user):
    """Create Authorization headers for an admin user."""
    with app.app_context():
        token = create_access_token(identity=admin_user.public_id)
        return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def user_factory(app):
    """Factory fixture to create test users."""
    def _create_user(username=None, email=None, role="user", is_active=True):
        import uuid
        uid = str(uuid.uuid4())[:8]
        user = User(
            username=username or f"user_{uid}",
            email=email or f"user_{uid}@example.com",
            password_hash=hash_password("Password123!"),
            role=role,
            is_active=is_active,
        )
        db.session.add(user)
        db.session.commit()
        return user
    return _create_user

