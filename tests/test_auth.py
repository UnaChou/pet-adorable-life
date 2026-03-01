"""Tests for authentication routes and the auth guard."""
from unittest.mock import patch
from werkzeug.security import generate_password_hash


# ===== Auth guard =====

def test_protected_page_redirects_to_login_when_unauthenticated(client, mock_db):
    res = client.get("/")
    assert res.status_code == 302
    assert "/login" in res.headers["Location"]


def test_protected_api_returns_401_when_unauthenticated(client, mock_db):
    res = client.get("/api/pets")
    assert res.status_code == 401
    assert "error" in res.get_json()


def test_login_page_accessible_unauthenticated(client, mock_db):
    res = client.get("/login")
    assert res.status_code == 200


def test_register_page_accessible_unauthenticated(client, mock_db):
    res = client.get("/register")
    assert res.status_code == 200


# ===== Login =====

def test_login_success_sets_session_and_redirects(client, mock_db):
    mock_db.get_user_by_username.return_value = {
        "id": 1,
        "username": "testuser",
        "password_hash": generate_password_hash("password1"),
    }
    res = client.post("/login", data={"username": "testuser", "password": "password1"})
    assert res.status_code == 302
    assert "/" in res.headers["Location"]
    with client.session_transaction() as sess:
        assert sess.get("user_id") == 1


def test_login_wrong_password_returns_401(client, mock_db):
    mock_db.get_user_by_username.return_value = {
        "id": 1,
        "username": "testuser",
        "password_hash": generate_password_hash("correctpass"),
    }
    res = client.post("/login", data={"username": "testuser", "password": "wrongpass"})
    assert res.status_code == 401


def test_login_unknown_user_returns_401(client, mock_db):
    mock_db.get_user_by_username.return_value = None
    res = client.post("/login", data={"username": "nobody", "password": "pass"})
    assert res.status_code == 401


# ===== Register =====

def test_register_success_creates_user_and_redirects(client, mock_db):
    mock_db.get_user_by_username.return_value = None
    mock_db.create_user.return_value = 5
    res = client.post("/register", data={
        "username": "newuser",
        "password": "securepass",
        "confirm_password": "securepass",
    })
    assert res.status_code == 302
    mock_db.create_user.assert_called_once()
    with client.session_transaction() as sess:
        assert sess.get("user_id") == 5


def test_register_duplicate_username_returns_400(client, mock_db):
    mock_db.get_user_by_username.return_value = {"id": 1, "username": "existinguser"}
    res = client.post("/register", data={
        "username": "existinguser",
        "password": "securepass",
        "confirm_password": "securepass",
    })
    assert res.status_code == 400


def test_register_password_mismatch_returns_400(client, mock_db):
    mock_db.get_user_by_username.return_value = None
    res = client.post("/register", data={
        "username": "newuser",
        "password": "password1",
        "confirm_password": "different1",
    })
    assert res.status_code == 400


def test_register_short_password_returns_400(client, mock_db):
    mock_db.get_user_by_username.return_value = None
    res = client.post("/register", data={
        "username": "newuser",
        "password": "short",
        "confirm_password": "short",
    })
    assert res.status_code == 400


def test_register_empty_username_returns_400(client, mock_db):
    res = client.post("/register", data={
        "username": "",
        "password": "securepass",
        "confirm_password": "securepass",
    })
    assert res.status_code == 400


def test_register_invalid_username_chars_returns_400(client, mock_db):
    mock_db.get_user_by_username.return_value = None
    res = client.post("/register", data={
        "username": "bad user!",
        "password": "securepass",
        "confirm_password": "securepass",
    })
    assert res.status_code == 400


# ===== Logout =====

def test_logout_clears_session_and_redirects_to_login(authed_client, mock_db):
    res = authed_client.get("/logout")
    assert res.status_code == 302
    assert "/login" in res.headers["Location"]
    with authed_client.session_transaction() as sess:
        assert "user_id" not in sess
