"""
E2E — Pet CRUD API tests.

Tests the full HTTP lifecycle of /api/pets against a live server and
real database. No mocking — these hit the actual MySQL backend.

Requires a live server: pytest tests/e2e/ --base-url http://localhost:5001
"""

import pytest


pytestmark = pytest.mark.e2e

# ---------------------------------------------------------------------------
# GET /api/pets
# ---------------------------------------------------------------------------

class TestGetPetsList:
    def test_returns_200(self, api):
        resp = api.get("/api/pets")
        assert resp.status_code == 200

    def test_response_has_pets_key(self, api):
        resp = api.get("/api/pets")
        body = resp.json()
        assert "pets" in body

    def test_pets_value_is_list(self, api):
        resp = api.get("/api/pets")
        assert isinstance(resp.json()["pets"], list)

    def test_content_type_is_json(self, api):
        resp = api.get("/api/pets")
        assert "application/json" in resp.headers.get("Content-Type", "")


# ---------------------------------------------------------------------------
# POST /api/pets
# ---------------------------------------------------------------------------

class TestCreatePet:
    def test_creates_pet_returns_201(self, api):
        resp = api.post("/api/pets", json={"name": "E2E小花"})
        assert resp.status_code == 201
        # cleanup
        api.delete(f"/api/pets/{resp.json()['id']}")

    def test_response_contains_pet_data(self, api):
        resp = api.post("/api/pets", json={"name": "E2E小白", "breed": "柴犬"})
        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == "E2E小白"
        assert body["breed"] == "柴犬"
        api.delete(f"/api/pets/{body['id']}")

    def test_response_contains_id(self, api):
        resp = api.post("/api/pets", json={"name": "E2E有ID"})
        assert "id" in resp.json()
        api.delete(f"/api/pets/{resp.json()['id']}")

    def test_empty_name_returns_400(self, api):
        resp = api.post("/api/pets", json={"name": ""})
        assert resp.status_code == 400

    def test_missing_name_key_returns_400(self, api):
        resp = api.post("/api/pets", json={"breed": "只有品種"})
        assert resp.status_code == 400

    def test_whitespace_only_name_returns_400(self, api):
        resp = api.post("/api/pets", json={"name": "   "})
        assert resp.status_code == 400

    def test_error_response_has_error_key(self, api):
        resp = api.post("/api/pets", json={"name": ""})
        assert "error" in resp.json()

    def test_pet_appears_in_list_after_creation(self, api):
        resp = api.post("/api/pets", json={"name": "E2E出現在列表"})
        pet_id = resp.json()["id"]
        list_resp = api.get("/api/pets")
        ids = [p["id"] for p in list_resp.json()["pets"]]
        assert pet_id in ids
        api.delete(f"/api/pets/{pet_id}")

    def test_pet_with_birthday(self, api):
        resp = api.post("/api/pets", json={"name": "E2E生日寵物", "birthday": "2022-03-15"})
        assert resp.status_code == 201
        assert resp.json()["birthday"] == "2022-03-15"
        api.delete(f"/api/pets/{resp.json()['id']}")


# ---------------------------------------------------------------------------
# GET /api/pets/<id>
# ---------------------------------------------------------------------------

class TestGetSinglePet:
    def test_returns_200_for_existing_pet(self, api, transient_pet):
        resp = api.get(f"/api/pets/{transient_pet['id']}")
        assert resp.status_code == 200

    def test_response_matches_created_pet(self, api, transient_pet):
        resp = api.get(f"/api/pets/{transient_pet['id']}")
        body = resp.json()
        assert body["id"] == transient_pet["id"]
        assert body["name"] == transient_pet["name"]

    def test_returns_404_for_nonexistent_pet(self, api):
        resp = api.get("/api/pets/999999999")
        assert resp.status_code == 404

    def test_404_response_has_error_key(self, api):
        resp = api.get("/api/pets/999999999")
        assert "error" in resp.json()

    def test_response_has_expected_fields(self, api, transient_pet):
        resp = api.get(f"/api/pets/{transient_pet['id']}")
        body = resp.json()
        for field in ("id", "name", "breed", "birthday", "photo_base64"):
            assert field in body, f"Field '{field}' missing from GET /api/pets/<id> response"


# ---------------------------------------------------------------------------
# PUT /api/pets/<id>
# ---------------------------------------------------------------------------

class TestUpdatePet:
    def test_returns_200(self, api, transient_pet):
        resp = api.put(
            f"/api/pets/{transient_pet['id']}",
            json={"name": "更新後名字", "breed": "更新品種"},
        )
        assert resp.status_code == 200

    def test_updated_fields_reflected_in_response(self, api, transient_pet):
        resp = api.put(
            f"/api/pets/{transient_pet['id']}",
            json={"name": "新名字", "breed": "新品種"},
        )
        body = resp.json()
        assert body["name"] == "新名字"
        assert body["breed"] == "新品種"

    def test_updated_fields_persisted_on_subsequent_get(self, api, transient_pet):
        api.put(
            f"/api/pets/{transient_pet['id']}",
            json={"name": "持久化名字"},
        )
        get_resp = api.get(f"/api/pets/{transient_pet['id']}")
        assert get_resp.json()["name"] == "持久化名字"

    def test_returns_404_for_nonexistent_pet(self, api):
        resp = api.put("/api/pets/999999999", json={"name": "幽靈"})
        assert resp.status_code == 404

    def test_empty_name_returns_400(self, api, transient_pet):
        resp = api.put(f"/api/pets/{transient_pet['id']}", json={"name": ""})
        assert resp.status_code == 400

    def test_birthday_can_be_updated(self, api, transient_pet):
        resp = api.put(
            f"/api/pets/{transient_pet['id']}",
            json={"name": transient_pet["name"], "birthday": "2020-06-01"},
        )
        assert resp.status_code == 200
        assert resp.json()["birthday"] == "2020-06-01"


# ---------------------------------------------------------------------------
# DELETE /api/pets/<id>
# ---------------------------------------------------------------------------

class TestDeletePet:
    def test_returns_204(self, api):
        create_resp = api.post("/api/pets", json={"name": "E2E待刪除"})
        pet_id = create_resp.json()["id"]
        resp = api.delete(f"/api/pets/{pet_id}")
        assert resp.status_code == 204

    def test_delete_response_body_is_empty(self, api):
        create_resp = api.post("/api/pets", json={"name": "E2E待刪除2"})
        pet_id = create_resp.json()["id"]
        resp = api.delete(f"/api/pets/{pet_id}")
        assert resp.content == b""

    def test_pet_no_longer_retrievable_after_delete(self, api):
        create_resp = api.post("/api/pets", json={"name": "E2E刪後消失"})
        pet_id = create_resp.json()["id"]
        api.delete(f"/api/pets/{pet_id}")
        get_resp = api.get(f"/api/pets/{pet_id}")
        assert get_resp.status_code == 404

    def test_pet_absent_from_list_after_delete(self, api):
        create_resp = api.post("/api/pets", json={"name": "E2E不在列表"})
        pet_id = create_resp.json()["id"]
        api.delete(f"/api/pets/{pet_id}")
        ids = [p["id"] for p in api.get("/api/pets").json()["pets"]]
        assert pet_id not in ids

    def test_returns_404_for_nonexistent_pet(self, api):
        resp = api.delete("/api/pets/999999999")
        assert resp.status_code == 404
