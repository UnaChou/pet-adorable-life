def test_get_medical_records(authed_client, mock_db):
    mock_db.get_all_medical_records.return_value = []
    res = authed_client.get("/api/medical-records")
    assert res.status_code == 200
    assert "medical_records" in res.get_json()


def test_get_medical_records_with_pet_filter(authed_client, mock_db):
    mock_db.get_all_medical_records.return_value = []
    mock_db.get_pet_accessible.return_value = {"id": 2, "name": "test"}
    authed_client.get("/api/medical-records?pet_id=2")
    mock_db.get_all_medical_records.assert_called_with(pet_id=2, user_id=None)


def test_add_medical_record_returns_201(authed_client, mock_db):
    mock_db.add_medical_record.return_value = 10
    mock_db.get_medical_record.return_value = {
        "id": 10, "title": "感冒就診", "description": "流鼻水",
        "occurred_date": "2024-03-15", "image_base64": "", "pet_id": None,
        "user_id": 1, "created_at": None, "updated_at": None,
    }
    res = authed_client.post("/api/medical-records", json={
        "title": "感冒就診", "description": "流鼻水", "occurred_date": "2024-03-15",
    })
    assert res.status_code == 201
    assert res.get_json()["id"] == 10


def test_get_medical_record_returns_200(authed_client, mock_db):
    mock_db.get_medical_record.return_value = {
        "id": 1, "title": "test", "description": "desc",
        "occurred_date": "2024-01-01", "image_base64": "",
        "pet_id": None, "user_id": 1, "created_at": None, "updated_at": None,
    }
    res = authed_client.get("/api/medical-records/1")
    assert res.status_code == 200
    assert res.get_json()["id"] == 1


def test_get_medical_record_not_found_returns_404(authed_client, mock_db):
    mock_db.get_medical_record.return_value = None
    res = authed_client.get("/api/medical-records/999")
    assert res.status_code == 404


def test_update_medical_record_returns_200(authed_client, mock_db):
    mock_db.get_medical_record_if_editable.return_value = {"id": 1, "title": "old"}
    mock_db.get_medical_record.return_value = {
        "id": 1, "title": "updated", "description": "new desc",
        "occurred_date": "2024-02-01", "image_base64": "",
        "pet_id": None, "user_id": 1, "created_at": None, "updated_at": None,
    }
    res = authed_client.put("/api/medical-records/1", json={
        "title": "updated", "description": "new desc", "occurred_date": "2024-02-01",
    })
    assert res.status_code == 200
    assert res.get_json()["title"] == "updated"


def test_update_medical_record_not_found_returns_404(authed_client, mock_db):
    mock_db.get_medical_record_if_editable.return_value = None
    res = authed_client.put("/api/medical-records/999", json={"title": "x"})
    assert res.status_code == 404


def test_delete_medical_record_returns_204(authed_client, mock_db):
    mock_db.get_medical_record_if_editable.return_value = {"id": 1, "title": "test"}
    res = authed_client.delete("/api/medical-records/1")
    assert res.status_code == 204
    mock_db.remove_medical_records.assert_called_once_with([1], user_id=1)


def test_delete_medical_record_not_found_returns_404(authed_client, mock_db):
    mock_db.get_medical_record_if_editable.return_value = None
    res = authed_client.delete("/api/medical-records/999")
    assert res.status_code == 404


def test_batch_delete_medical_records_returns_204(authed_client, mock_db):
    res = authed_client.delete("/api/medical-records", json={"ids": [1, 2]})
    assert res.status_code == 204
    mock_db.remove_medical_records.assert_called_once_with([1, 2], user_id=1)


def test_add_medical_record_db_failure_returns_500(authed_client, mock_db):
    mock_db.add_medical_record.return_value = 99
    mock_db.get_medical_record.return_value = None
    res = authed_client.post("/api/medical-records", json={
        "title": "T", "description": "D", "occurred_date": "2024-01-01",
    })
    assert res.status_code == 500


def test_summary_no_pet_returns_400(authed_client, mock_db):
    res = authed_client.post("/api/medical-records/summary", json={})
    assert res.status_code == 400


def test_summary_no_records_returns_400(authed_client, mock_db):
    mock_db.get_medical_records_for_summary.return_value = []
    res = authed_client.post("/api/medical-records/summary", json={"pet_id": 1})
    assert res.status_code == 400


def test_get_latest_summary_returns_none(authed_client, mock_db):
    mock_db.get_latest_medical_summary.return_value = None
    res = authed_client.get("/api/medical-records/summary/latest?pet_id=1")
    assert res.status_code == 200
    assert res.get_json()["summary"] is None


def test_get_latest_summary_returns_data(authed_client, mock_db):
    mock_db.get_latest_medical_summary.return_value = {
        "id": 1, "pet_id": 1, "summary_text": "測試摘要", "created_at": None,
    }
    res = authed_client.get("/api/medical-records/summary/latest?pet_id=1")
    assert res.status_code == 200
    assert res.get_json()["summary"]["summary_text"] == "測試摘要"
