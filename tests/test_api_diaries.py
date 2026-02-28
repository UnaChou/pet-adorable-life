def test_get_diaries(client, mock_db):
    mock_db.get_all_diaries.return_value = []
    res = client.get("/api/diaries")
    assert res.status_code == 200
    assert "diaries" in res.get_json()


def test_get_diaries_with_pet_filter(client, mock_db):
    mock_db.get_all_diaries.return_value = []
    client.get("/api/diaries?pet_id=2")
    mock_db.get_all_diaries.assert_called_with(pet_id=2)


def test_add_diary_returns_201(client, mock_db):
    mock_db.add_diary.return_value = 7
    mock_db.get_diary.return_value = {"id": 7, "title": "今天", "describe_text": "開心", "main_emotion": "快樂", "memo": "", "image_base64": "", "pet_id": None, "created_at": None, "updated_at": None}
    res = client.post("/api/diaries", json={"title": "今天", "describe_text": "開心", "main_emotion": "快樂", "memo": ""})
    assert res.status_code == 201
    assert res.get_json()["id"] == 7


def test_delete_diary_returns_204(client, mock_db):
    mock_db.get_diary.return_value = {"id": 1, "title": "日記"}
    res = client.delete("/api/diaries/1")
    assert res.status_code == 204
    mock_db.remove_diaries.assert_called_once_with([1])


def test_delete_diary_not_found_returns_404(client, mock_db):
    mock_db.get_diary.return_value = None
    res = client.delete("/api/diaries/999")
    assert res.status_code == 404


def test_batch_delete_diaries_returns_204(client, mock_db):
    res = client.delete("/api/diaries", json={"ids": [1, 2]})
    assert res.status_code == 204
    mock_db.remove_diaries.assert_called_once_with([1, 2])
