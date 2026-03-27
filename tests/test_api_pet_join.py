import pytest
import hashlib
from datetime import datetime, timedelta
from unittest.mock import patch


def _make_inv(status="pending", invitee_id=1):
    return {
        "id": 99,
        "pet_id": 1,
        "inviter_user_id": 2,
        "invitee_user_id": invitee_id,
        "role": "read_only",
        "status": status,
        "expires_at": datetime.utcnow() + timedelta(days=7),
        "inviter_username": "bob",
        "pet_name": "毛球",
    }


def test_join_page_requires_login(client, mock_db):
    mock_db.get_pet_share_invitation_by_token.return_value = _make_inv()
    res = client.get("/pets/join/sometoken123456789012345678901234")
    # Should redirect to login (not 200 or 404)
    assert res.status_code == 302
    assert "/login" in res.headers["Location"]


def test_join_page_shows_invitation_when_logged_in(authed_client, mock_db):
    mock_db.get_pet_share_invitation_by_token.return_value = _make_inv(invitee_id=1)
    res = authed_client.get("/pets/join/sometoken123456789012345678901234")
    assert res.status_code == 200
    assert "毛球" in res.get_data(as_text=True)


def test_join_page_wrong_user_shows_error(authed_client, mock_db):
    # authed_client is user_id=1; invitation is for user_id=99
    mock_db.get_pet_share_invitation_by_token.return_value = _make_inv(invitee_id=99)
    res = authed_client.get("/pets/join/sometoken123456789012345678901234")
    assert res.status_code == 200
    assert "邀請連結無效或已過期" in res.get_data(as_text=True)


def test_accept_invitation(authed_client, mock_db):
    mock_db.get_pet_share_invitation_by_token.return_value = _make_inv(invitee_id=1)
    mock_db.accept_pet_share_invitation.return_value = True
    with patch("app._validate_csrf_token", return_value=True):
        res = authed_client.post("/pets/join/sometoken123456789012345678901234", data={"action": "accept"})
    assert res.status_code in (302, 200)


def test_decline_invitation(authed_client, mock_db):
    mock_db.get_pet_share_invitation_by_token.return_value = _make_inv(invitee_id=1)
    mock_db.decline_pet_share_invitation.return_value = 1
    with patch("app._validate_csrf_token", return_value=True):
        res = authed_client.post("/pets/join/sometoken123456789012345678901234", data={"action": "decline"})
    assert res.status_code in (302, 200)


def test_login_preserves_next_url(client, mock_db):
    """_require_login should append ?next= when redirecting unauthenticated users."""
    res = client.get("/pets/join/sometoken123456789012345678901234")
    assert res.status_code == 302
    assert "next=" in res.headers["Location"]
