"""Tests for page routes and analyze API endpoints."""
from io import BytesIO
from unittest.mock import patch


def test_index_page(authed_client, mock_db):
    res = authed_client.get("/")
    assert res.status_code == 200


def test_product_analyze_page(authed_client, mock_db):
    res = authed_client.get("/product/analyze")
    assert res.status_code == 200


def test_organize_page(authed_client, mock_db):
    res = authed_client.get("/organize")
    assert res.status_code == 200


def test_organize_edit_page(authed_client, mock_db):
    res = authed_client.get("/organize/edit/42")
    assert res.status_code == 200


def test_diary_page(authed_client, mock_db):
    res = authed_client.get("/diary")
    assert res.status_code == 200


def test_pets_page(authed_client, mock_db):
    res = authed_client.get("/pets")
    assert res.status_code == 200


# ===== /api/product/analyze =====

def _post_image(c, path, filename="test.jpg", data=b"img"):
    return c.post(
        path,
        data={"image": (BytesIO(data), filename)},
        content_type="multipart/form-data",
    )


def test_product_analyze_no_image_returns_400(authed_client, mock_db):
    res = authed_client.post("/api/product/analyze")
    assert res.status_code == 400
    assert "error" in res.get_json()


def test_product_analyze_empty_filename_returns_400(authed_client, mock_db):
    res = authed_client.post(
        "/api/product/analyze",
        data={"image": (BytesIO(b"x"), "")},
        content_type="multipart/form-data",
    )
    assert res.status_code == 400


def test_product_analyze_unsupported_format_returns_400(authed_client, mock_db):
    res = _post_image(authed_client, "/api/product/analyze", filename="file.pdf")
    assert res.status_code == 400
    assert "不支援" in res.get_json()["error"]


def test_product_analyze_model_returns_none_returns_500(authed_client, mock_db):
    with patch("app.model_connector.get_model_response_by_image", return_value=None):
        res = _post_image(authed_client, "/api/product/analyze")
    assert res.status_code == 500


def test_product_analyze_model_returns_error_returns_500(authed_client, mock_db):
    with patch("app.model_connector.get_model_response_by_image", return_value={"error": "失敗"}):
        res = _post_image(authed_client, "/api/product/analyze")
    assert res.status_code == 500


def test_product_analyze_success(authed_client, mock_db):
    with patch("app.model_connector.get_model_response_by_image",
               return_value={"title": "飼料", "summary": "好吃"}):
        res = _post_image(authed_client, "/api/product/analyze")
    assert res.status_code == 200
    assert res.get_json()["title"] == "飼料"


def test_product_analyze_webp_allowed(authed_client, mock_db):
    with patch("app.model_connector.get_model_response_by_image",
               return_value={"title": "X", "summary": "Y"}):
        res = _post_image(authed_client, "/api/product/analyze", filename="photo.webp")
    assert res.status_code == 200


# ===== /api/diary/analyze =====

def test_diary_analyze_no_image_returns_400(authed_client, mock_db):
    res = authed_client.post("/api/diary/analyze")
    assert res.status_code == 400


def test_diary_analyze_empty_filename_returns_400(authed_client, mock_db):
    res = authed_client.post(
        "/api/diary/analyze",
        data={"image": (BytesIO(b"x"), "")},
        content_type="multipart/form-data",
    )
    assert res.status_code == 400


def test_diary_analyze_unsupported_format_returns_400(authed_client, mock_db):
    res = _post_image(authed_client, "/api/diary/analyze", filename="doc.pdf")
    assert res.status_code == 400


def test_diary_analyze_model_returns_none_returns_500(authed_client, mock_db):
    with patch("app.model_connector.get_diary_response_by_image", return_value=None):
        res = _post_image(authed_client, "/api/diary/analyze")
    assert res.status_code == 500


def test_diary_analyze_model_returns_error_returns_500(authed_client, mock_db):
    with patch("app.model_connector.get_diary_response_by_image",
               return_value={"error": "分析失敗"}):
        res = _post_image(authed_client, "/api/diary/analyze")
    assert res.status_code == 500


def test_diary_analyze_success(authed_client, mock_db):
    with patch("app.model_connector.get_diary_response_by_image",
               return_value={"title": "快樂", "describe": "很開心", "main_emotion": "開心"}):
        res = _post_image(authed_client, "/api/diary/analyze")
    assert res.status_code == 200
    data = res.get_json()
    assert data["main_emotion"] == "開心"
    assert data["describe"] == "很開心"


def test_diary_analyze_exception_returns_500(authed_client, mock_db):
    with patch("app.model_connector.get_diary_response_by_image", side_effect=RuntimeError("boom")):
        res = _post_image(authed_client, "/api/diary/analyze")
    assert res.status_code == 500
    assert "error" in res.get_json()


# ===== Additional app.py branch coverage =====

def test_add_pet_null_return_returns_500(authed_client, mock_db):
    """Guard: add_pet succeeds but get_pet returns None → 500."""
    mock_db.add_pet.return_value = 99
    mock_db.get_pet.return_value = None
    res = authed_client.post("/api/pets", json={"name": "小白"})
    assert res.status_code == 500


def test_get_pet_found_returns_200(authed_client, mock_db):
    mock_db.get_pet.return_value = {"id": 1, "name": "小黑", "breed": "", "birthday": "", "photo_base64": "", "created_at": None, "updated_at": None}
    res = authed_client.get("/api/pets/1")
    assert res.status_code == 200
    assert res.get_json()["name"] == "小黑"


def test_update_pet_not_found_returns_404(authed_client, mock_db):
    mock_db.get_pet.return_value = None
    res = authed_client.put("/api/pets/999", json={"name": "X"})
    assert res.status_code == 404


def test_delete_pet_not_found_returns_404(authed_client, mock_db):
    mock_db.get_pet.return_value = None
    res = authed_client.delete("/api/pets/999")
    assert res.status_code == 404


def test_add_product_null_return_returns_500(authed_client, mock_db):
    """Guard: add_product succeeds but get_product returns None → 500."""
    mock_db.add_product.return_value = 77
    mock_db.get_product.return_value = None
    res = authed_client.post("/api/products", json={"title": "T", "summary": "S"})
    assert res.status_code == 500


def test_batch_delete_products_empty_ids(authed_client, mock_db):
    """DELETE /api/products with empty ids list."""
    res = authed_client.delete("/api/products", json={"ids": []})
    assert res.status_code == 204
    mock_db.remove_products.assert_not_called()
