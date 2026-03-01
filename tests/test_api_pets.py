import pytest


def test_get_pets_returns_list(authed_client, mock_db):
    mock_db.get_all_pets.return_value = []
    res = authed_client.get("/api/pets")
    assert res.status_code == 200
    assert res.get_json() == {"pets": []}


def test_add_pet_returns_201(authed_client, mock_db):
    mock_db.add_pet.return_value = 1
    mock_db.get_pet.return_value = {"id": 1, "name": "小黑", "breed": "柴犬", "birthday": "", "photo_base64": "", "created_at": None, "updated_at": None}
    res = authed_client.post("/api/pets", json={"name": "小黑", "breed": "柴犬"})
    assert res.status_code == 201
    assert res.get_json()["name"] == "小黑"


def test_add_pet_missing_name_returns_400(authed_client, mock_db):
    res = authed_client.post("/api/pets", json={"breed": "柴犬"})
    assert res.status_code == 400


def test_get_pet_not_found_returns_404(authed_client, mock_db):
    mock_db.get_pet.return_value = None
    res = authed_client.get("/api/pets/999")
    assert res.status_code == 404


def test_update_pet_returns_200(authed_client, mock_db):
    pet = {"id": 1, "name": "大黑", "breed": "柴犬", "birthday": "", "photo_base64": "", "created_at": None, "updated_at": None}
    mock_db.get_pet.return_value = pet
    res = authed_client.put("/api/pets/1", json={"name": "大黑", "breed": "柴犬"})
    assert res.status_code == 200


def test_delete_pet_returns_204(authed_client, mock_db):
    mock_db.get_pet.return_value = {"id": 1, "name": "小黑"}
    res = authed_client.delete("/api/pets/1")
    assert res.status_code == 204
    mock_db.remove_pet.assert_called_once_with(1, user_id=1)


def test_update_pet_missing_name_returns_400(authed_client, mock_db):
    mock_db.get_pet.return_value = {"id": 1, "name": "小黑"}
    res = authed_client.put("/api/pets/1", json={"name": ""})
    assert res.status_code == 400
