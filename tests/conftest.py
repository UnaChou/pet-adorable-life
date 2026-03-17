import pytest
from unittest.mock import patch
from app import app as flask_app


@pytest.fixture
def client():
    flask_app.config["TESTING"] = True
    flask_app._db_initialized = False
    with flask_app.test_client() as c:
        yield c
    flask_app._db_initialized = False


@pytest.fixture
def authed_client(client):
    """Client with user_id=1 already in session (simulates logged-in user)."""
    with client.session_transaction() as sess:
        sess["user_id"] = 1
    yield client


@pytest.fixture
def mock_db():
    """Patch the db module in app so no real DB calls happen."""
    with patch("app.db") as m:
        yield m
