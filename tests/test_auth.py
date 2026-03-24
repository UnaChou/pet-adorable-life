"""Tests for authentication routes and the auth guard."""
import re
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from werkzeug.security import generate_password_hash


# ===== Auth guard =====


def _extract_csrf_token(html: str) -> str:
    match = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
    assert match
    return match.group(1)

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

def test_login_requires_csrf_token(client, mock_db):
    res = client.post("/login", data={"username": "testuser", "password": "password1"})
    assert res.status_code == 400
    mock_db.get_user_by_username.assert_not_called()


def test_login_success_sets_session_and_redirects(client, mock_db):
    mock_db.get_user_by_username.return_value = {
        "id": 1,
        "username": "testuser",
        "password_hash": generate_password_hash("password1"),
    }
    page = client.get("/login")
    csrf_token = _extract_csrf_token(page.get_data(as_text=True))
    res = client.post("/login", data={"username": "testuser", "password": "password1", "csrf_token": csrf_token})
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
    page = client.get("/login")
    csrf_token = _extract_csrf_token(page.get_data(as_text=True))
    res = client.post("/login", data={"username": "testuser", "password": "wrongpass", "csrf_token": csrf_token})
    assert res.status_code == 401


def test_login_unknown_user_returns_401(client, mock_db):
    mock_db.get_user_by_username.return_value = None
    page = client.get("/login")
    csrf_token = _extract_csrf_token(page.get_data(as_text=True))
    res = client.post("/login", data={"username": "nobody", "password": "pass", "csrf_token": csrf_token})
    assert res.status_code == 401


def test_login_json_requires_csrf_token(client, mock_db):
    res = client.post(
        "/login",
        json={"username": "testuser", "password": "password1"},
    )
    assert res.status_code == 400
    assert res.get_json()["error"] == "表單已失效，請再試一次"
    assert res.get_json()["csrf_token"]
    mock_db.get_user_by_username.assert_not_called()


def test_login_json_success_sets_session_and_returns_redirect(client, mock_db):
    mock_db.get_user_by_username.return_value = {
        "id": 1,
        "username": "testuser",
        "password_hash": generate_password_hash("password1"),
    }
    page = client.get("/login")
    csrf_token = _extract_csrf_token(page.get_data(as_text=True))
    res = client.post(
        "/login",
        json={"username": "testuser", "password": "password1", "csrf_token": csrf_token},
    )
    assert res.status_code == 200
    assert res.get_json() == {"ok": True, "redirect_to": "/"}
    with client.session_transaction() as sess:
        assert sess.get("user_id") == 1


def test_login_json_wrong_password_returns_401_and_fresh_csrf(client, mock_db):
    mock_db.get_user_by_username.return_value = {
        "id": 1,
        "username": "testuser",
        "password_hash": generate_password_hash("correctpass"),
    }
    page = client.get("/login")
    csrf_token = _extract_csrf_token(page.get_data(as_text=True))
    res = client.post(
        "/login",
        json={"username": "testuser", "password": "wrongpass", "csrf_token": csrf_token},
    )
    assert res.status_code == 401
    assert res.get_json()["error"] == "帳號或密碼錯誤"
    assert res.get_json()["csrf_token"]


# ===== Register =====

def test_register_requires_csrf_token(client, mock_db):
    res = client.post("/register", data={
        "username": "newuser",
        "email": "newuser@example.com",
        "password": "securepass",
        "confirm_password": "securepass",
    })
    assert res.status_code == 400
    mock_db.get_user_by_username.assert_not_called()
    mock_db.get_user_by_email.assert_not_called()
    mock_db.create_user.assert_not_called()


def test_register_success_creates_user_and_redirects(client, mock_db):
    mock_db.get_user_by_username.return_value = None
    mock_db.get_user_by_email.return_value = None
    mock_db.create_user.return_value = 5
    page = client.get("/register")
    csrf_token = _extract_csrf_token(page.get_data(as_text=True))
    res = client.post("/register", data={
        "username": "newuser",
        "email": "newuser@example.com",
        "password": "securepass",
        "confirm_password": "securepass",
        "csrf_token": csrf_token,
    })
    assert res.status_code == 302
    mock_db.create_user.assert_called_once()
    called_args = mock_db.create_user.call_args[0]
    assert called_args[0] == "newuser"
    assert called_args[1] == "newuser@example.com"
    with client.session_transaction() as sess:
        assert sess.get("user_id") == 5


def test_register_duplicate_username_returns_400(client, mock_db):
    mock_db.get_user_by_username.return_value = {"id": 1, "username": "existinguser"}
    page = client.get("/register")
    csrf_token = _extract_csrf_token(page.get_data(as_text=True))
    res = client.post("/register", data={
        "username": "existinguser",
        "email": "existing@example.com",
        "password": "securepass",
        "confirm_password": "securepass",
        "csrf_token": csrf_token,
    })
    assert res.status_code == 400


def test_register_password_mismatch_returns_400(client, mock_db):
    mock_db.get_user_by_username.return_value = None
    mock_db.get_user_by_email.return_value = None
    page = client.get("/register")
    csrf_token = _extract_csrf_token(page.get_data(as_text=True))
    res = client.post("/register", data={
        "username": "newuser",
        "email": "newuser@example.com",
        "password": "password1",
        "confirm_password": "different1",
        "csrf_token": csrf_token,
    })
    assert res.status_code == 400


def test_register_short_password_returns_400(client, mock_db):
    mock_db.get_user_by_username.return_value = None
    mock_db.get_user_by_email.return_value = None
    page = client.get("/register")
    csrf_token = _extract_csrf_token(page.get_data(as_text=True))
    res = client.post("/register", data={
        "username": "newuser",
        "email": "newuser@example.com",
        "password": "short",
        "confirm_password": "short",
        "csrf_token": csrf_token,
    })
    assert res.status_code == 400


def test_register_empty_username_returns_400(client, mock_db):
    page = client.get("/register")
    csrf_token = _extract_csrf_token(page.get_data(as_text=True))
    res = client.post("/register", data={
        "username": "",
        "email": "newuser@example.com",
        "password": "securepass",
        "confirm_password": "securepass",
        "csrf_token": csrf_token,
    })
    assert res.status_code == 400


def test_register_invalid_username_chars_returns_400(client, mock_db):
    mock_db.get_user_by_username.return_value = None
    mock_db.get_user_by_email.return_value = None
    page = client.get("/register")
    csrf_token = _extract_csrf_token(page.get_data(as_text=True))
    res = client.post("/register", data={
        "username": "bad user!",
        "email": "newuser@example.com",
        "password": "securepass",
        "confirm_password": "securepass",
        "csrf_token": csrf_token,
    })
    assert res.status_code == 400


def test_register_duplicate_email_returns_400(client, mock_db):
    mock_db.get_user_by_username.return_value = None
    mock_db.get_user_by_email.return_value = {
        "id": 1,
        "username": "existinguser",
        "email": "used@example.com",
    }
    page = client.get("/register")
    csrf_token = _extract_csrf_token(page.get_data(as_text=True))
    res = client.post("/register", data={
        "username": "newuser",
        "email": "used@example.com",
        "password": "securepass",
        "confirm_password": "securepass",
        "csrf_token": csrf_token,
    })
    assert res.status_code == 400


def test_forgot_password_requires_csrf_token(client, mock_db):
    res = client.post("/forgot-password", data={"email": "user@example.com"})
    assert res.status_code == 400


def test_forgot_password_creates_token_with_valid_csrf(client, mock_db):
    mock_db.get_user_by_email.return_value = {
        "id": 8,
        "email": "user@example.com",
        "username": "user1",
    }
    mock_db.count_recent_reset_requests.return_value = 0

    page = client.get("/forgot-password")
    csrf_token = _extract_csrf_token(page.get_data(as_text=True))

    with patch("app.mail.send") as mock_send:
        res = client.post("/forgot-password", data={
            "email": "user@example.com",
            "csrf_token": csrf_token,
        })

    assert res.status_code == 302
    mock_db.create_reset_token.assert_called_once()
    mock_send.assert_called_once()


def test_forgot_password_rate_limited_skips_db_lookup(client, mock_db):
    page = client.get("/forgot-password")
    csrf_token = _extract_csrf_token(page.get_data(as_text=True))

    with patch("app._is_forgot_password_rate_limited", return_value=True):
        res = client.post("/forgot-password", data={
            "email": "user@example.com",
            "csrf_token": csrf_token,
        })

    assert res.status_code == 302
    mock_db.get_user_by_email.assert_not_called()


def test_reset_password_rejects_invalid_token_format(client, mock_db):
    res = client.get("/reset-password/invalid***")
    assert res.status_code == 200
    mock_db.get_reset_token.assert_not_called()


def test_reset_password_requires_csrf_token(client, mock_db):
    token = "A" * 43
    mock_db.get_reset_token.return_value = {
        "id": 12,
        "user_id": 3,
        "used_at": None,
        "expires_at": datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=30),
    }

    res = client.post(f"/reset-password/{token}", data={
        "new_password": "new-password1",
        "confirm_password": "new-password1",
    })
    assert res.status_code == 400
    mock_db.update_user_password.assert_not_called()


def test_reset_password_success_clears_session_and_updates_password(authed_client, mock_db):
    token = "B" * 43
    mock_db.get_reset_token.return_value = {
        "id": 22,
        "user_id": 1,
        "used_at": None,
        "expires_at": datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=30),
    }

    page = authed_client.get(f"/reset-password/{token}")
    csrf_token = _extract_csrf_token(page.get_data(as_text=True))

    res = authed_client.post(f"/reset-password/{token}", data={
        "new_password": "new-password1",
        "confirm_password": "new-password1",
        "csrf_token": csrf_token,
    })

    assert res.status_code == 302
    mock_db.invalidate_user_reset_tokens.assert_called_once_with(1)
    mock_db.mark_reset_token_used.assert_called_once_with(22)
    mock_db.update_user_password.assert_called_once()
    with authed_client.session_transaction() as sess:
        assert "user_id" not in sess


# ===== Forgot Password edge cases =====

def test_forgot_password_unknown_email_still_redirects(client, mock_db):
    """Unknown email must redirect without error — prevents email enumeration."""
    mock_db.get_user_by_email.return_value = None
    page = client.get("/forgot-password")
    csrf_token = _extract_csrf_token(page.get_data(as_text=True))

    res = client.post("/forgot-password", data={
        "email": "nobody@example.com",
        "csrf_token": csrf_token,
    })

    assert res.status_code == 302
    mock_db.create_reset_token.assert_not_called()


def test_forgot_password_invalid_email_format_still_redirects(client, mock_db):
    page = client.get("/forgot-password")
    csrf_token = _extract_csrf_token(page.get_data(as_text=True))

    res = client.post("/forgot-password", data={
        "email": "not-an-email",
        "csrf_token": csrf_token,
    })

    assert res.status_code == 302
    mock_db.get_user_by_email.assert_not_called()


# ===== Reset Password edge cases =====

def test_reset_password_expired_token_shows_error(client, mock_db):
    token = "C" * 43
    mock_db.get_reset_token.return_value = {
        "id": 5,
        "user_id": 3,
        "used_at": None,
        "expires_at": datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=2),
    }

    res = client.get(f"/reset-password/{token}")

    assert res.status_code == 200
    assert "過期" in res.get_data(as_text=True)
    mock_db.update_user_password.assert_not_called()


def test_reset_password_already_used_token_shows_error(client, mock_db):
    token = "D" * 43
    mock_db.get_reset_token.return_value = {
        "id": 6,
        "user_id": 3,
        "used_at": datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=5),
        "expires_at": datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=1),
    }

    res = client.get(f"/reset-password/{token}")

    assert res.status_code == 200
    assert "已使用" in res.get_data(as_text=True)
    mock_db.update_user_password.assert_not_called()


def test_reset_password_mismatched_passwords_returns_400(client, mock_db):
    token = "E" * 43
    mock_db.get_reset_token.return_value = {
        "id": 7,
        "user_id": 3,
        "used_at": None,
        "expires_at": datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=1),
    }

    page = client.get(f"/reset-password/{token}")
    csrf_token = _extract_csrf_token(page.get_data(as_text=True))

    res = client.post(f"/reset-password/{token}", data={
        "new_password": "password123",
        "confirm_password": "different123",
        "csrf_token": csrf_token,
    })

    assert res.status_code == 400
    mock_db.update_user_password.assert_not_called()


def test_reset_password_short_password_returns_400(client, mock_db):
    token = "F" * 43
    mock_db.get_reset_token.return_value = {
        "id": 8,
        "user_id": 3,
        "used_at": None,
        "expires_at": datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=1),
    }

    page = client.get(f"/reset-password/{token}")
    csrf_token = _extract_csrf_token(page.get_data(as_text=True))

    res = client.post(f"/reset-password/{token}", data={
        "new_password": "short",
        "confirm_password": "short",
        "csrf_token": csrf_token,
    })

    assert res.status_code == 400
    mock_db.update_user_password.assert_not_called()


# ===== Logout =====

def test_logout_clears_session_and_redirects_to_login(authed_client, mock_db):
    res = authed_client.get("/logout")
    assert res.status_code == 302
    assert "/login" in res.headers["Location"]
    with authed_client.session_transaction() as sess:
        assert "user_id" not in sess
