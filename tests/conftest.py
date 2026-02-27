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
def mock_db():
    """Patch the db module in app so no real DB calls happen."""
    with patch("app.db") as m:
        yield m
