import pytest

_PET_OWNED = {
    "id": 1, "name": "毛球", "breed": "", "birthday": "",
    "photo_base64": "", "user_id": 1, "is_shared": False,
    "created_at": None, "updated_at": None,
}
_PET_SHARED = {**_PET_OWNED, "user_id": 2, "is_shared": True}


# ── GET /api/pets/<id> — accessible by shared user ───────────────────────

def test_get_pet_uses_accessible(authed_client, mock_db):
    mock_db.get_pet_accessible.return_value = _PET_SHARED
    res = authed_client.get("/api/pets/1")
    assert res.status_code == 200
    assert res.get_json()["is_shared"] is True


# ── PUT /api/pets/<id> — editor can update, read-only cannot ─────────────

def test_update_pet_editor_allowed(authed_client, mock_db):
    mock_db.get_pet_if_editable.return_value = _PET_SHARED
    mock_db.get_pet_accessible.return_value = _PET_SHARED
    res = authed_client.put("/api/pets/1", json={"name": "毛球改"})
    assert res.status_code == 200


def test_update_pet_read_only_returns_404(authed_client, mock_db):
    mock_db.get_pet_if_editable.return_value = None
    res = authed_client.put("/api/pets/1", json={"name": "毛球改"})
    assert res.status_code == 404


# ── GET /api/pets/<id>/shares ─────────────────────────────────────────────

def test_get_shares_returns_list(authed_client, mock_db):
    mock_db.get_pet.return_value = _PET_OWNED
    mock_db.get_pet_shares.return_value = [
        {"id": 10, "shared_with_user_id": 2, "username": "alice", "role": "editor"}
    ]
    res = authed_client.get("/api/pets/1/shares")
    assert res.status_code == 200
    assert res.get_json()["shares"][0]["role"] == "editor"


def test_get_shares_non_owner_returns_404(authed_client, mock_db):
    mock_db.get_pet.return_value = None
    res = authed_client.get("/api/pets/1/shares")
    assert res.status_code == 404


# ── DELETE /api/pets/<id>/shares/<share_id> ──────────────────────────────

def test_remove_share_success(authed_client, mock_db):
    mock_db.get_pet.return_value = _PET_OWNED
    mock_db.remove_pet_share.return_value = 1
    res = authed_client.delete("/api/pets/1/shares/10")
    assert res.status_code == 204


def test_remove_share_not_found_returns_404(authed_client, mock_db):
    mock_db.get_pet.return_value = _PET_OWNED
    mock_db.remove_pet_share.return_value = 0
    res = authed_client.delete("/api/pets/1/shares/10")
    assert res.status_code == 404


# ── POST /api/pets/<id>/invitations ──────────────────────────────────────

def test_send_invitation_success(authed_client, mock_db):
    mock_db.get_pet.return_value = _PET_OWNED
    mock_db.get_user_by_username.return_value = {"id": 2, "username": "alice", "email": "alice@test.com"}
    mock_db.get_user_by_id.return_value = {"id": 1, "username": "me"}
    mock_db.is_pet_co_owner.return_value = False
    mock_db.create_pet_share_invitation.return_value = 5
    res = authed_client.post("/api/pets/1/invitations", json={"username": "alice", "role": "read_only"})
    assert res.status_code == 201
    assert res.get_json()["invitee_username"] == "alice"


def test_send_invitation_no_email_returns_400(authed_client, mock_db):
    mock_db.get_pet.return_value = _PET_OWNED
    mock_db.get_user_by_username.return_value = {"id": 2, "username": "alice", "email": None}
    res = authed_client.post("/api/pets/1/invitations", json={"username": "alice", "role": "read_only"})
    assert res.status_code == 400


def test_send_invitation_invalid_role_returns_400(authed_client, mock_db):
    mock_db.get_pet.return_value = _PET_OWNED
    mock_db.get_user_by_username.return_value = {"id": 2, "username": "alice", "email": "alice@test.com"}
    res = authed_client.post("/api/pets/1/invitations", json={"username": "alice", "role": "superadmin"})
    assert res.status_code == 400


def test_send_invitation_self_returns_400(authed_client, mock_db):
    mock_db.get_pet.return_value = _PET_OWNED
    # authed_client user_id=1; target also id=1
    mock_db.get_user_by_username.return_value = {"id": 1, "username": "me", "email": "me@test.com"}
    res = authed_client.post("/api/pets/1/invitations", json={"username": "me", "role": "read_only"})
    assert res.status_code == 400


def test_send_invitation_non_owner_returns_404(authed_client, mock_db):
    mock_db.get_pet.return_value = None
    res = authed_client.post("/api/pets/1/invitations", json={"username": "alice", "role": "read_only"})
    assert res.status_code == 404


def test_send_invitation_unknown_user_returns_404(authed_client, mock_db):
    mock_db.get_pet.return_value = _PET_OWNED
    mock_db.get_user_by_username.return_value = None
    res = authed_client.post("/api/pets/1/invitations", json={"username": "nobody", "role": "read_only"})
    assert res.status_code == 404


# ── GET /api/pets/<id>/invitations ────────────────────────────────────────

def test_list_invitations(authed_client, mock_db):
    mock_db.get_pet.return_value = _PET_OWNED
    mock_db.get_pet_invitations_for_pet.return_value = [
        {"id": 7, "invitee_username": "alice", "role": "read_only", "expires_at": None, "created_at": None}
    ]
    res = authed_client.get("/api/pets/1/invitations")
    assert res.status_code == 200
    assert len(res.get_json()["invitations"]) == 1


# ── DELETE /api/pets/<id>/invitations/<inv_id> ───────────────────────────

def test_cancel_invitation_success(authed_client, mock_db):
    mock_db.get_pet.return_value = _PET_OWNED
    mock_db.cancel_pet_share_invitation.return_value = 1
    res = authed_client.delete("/api/pets/1/invitations/7")
    assert res.status_code == 204


def test_cancel_invitation_not_found_returns_404(authed_client, mock_db):
    mock_db.get_pet.return_value = _PET_OWNED
    mock_db.cancel_pet_share_invitation.return_value = 0
    res = authed_client.delete("/api/pets/1/invitations/7")
    assert res.status_code == 404
