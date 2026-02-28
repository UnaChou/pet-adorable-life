def test_get_products(client, mock_db):
    mock_db.get_all_products.return_value = []
    res = client.get("/api/products")
    assert res.status_code == 200
    assert "products" in res.get_json()


def test_get_products_with_pet_filter(client, mock_db):
    mock_db.get_all_products.return_value = []
    res = client.get("/api/products?pet_id=1")
    assert res.status_code == 200
    mock_db.get_all_products.assert_called_with(pet_id=1)


def test_add_product_returns_201(client, mock_db):
    mock_db.add_product.return_value = 5
    mock_db.get_product.return_value = {"id": 5, "title": "飼料", "summary": "", "pet_id": None, "created_at": None, "updated_at": None}
    res = client.post("/api/products", json={"title": "飼料", "summary": ""})
    assert res.status_code == 201
    assert res.get_json()["id"] == 5


def test_update_product_not_found_returns_404(client, mock_db):
    mock_db.get_product.return_value = None
    res = client.put("/api/products/999", json={"title": "x"})
    assert res.status_code == 404


def test_delete_product_returns_204(client, mock_db):
    mock_db.get_product.return_value = {"id": 1}
    res = client.delete("/api/products/1")
    assert res.status_code == 204
    mock_db.remove_product.assert_called_once_with(1)


def test_batch_delete_products_returns_204(client, mock_db):
    res = client.delete("/api/products", json={"ids": [1, 2, 3]})
    assert res.status_code == 204
    mock_db.remove_products.assert_called_once_with([1, 2, 3])


def test_get_product_returns_200(client, mock_db):
    mock_db.get_product.return_value = {"id": 1, "title": "T", "summary": "S", "pet_id": None, "created_at": None, "updated_at": None}
    res = client.get("/api/products/1")
    assert res.status_code == 200
    assert res.get_json()["id"] == 1


def test_get_product_not_found_returns_404(client, mock_db):
    mock_db.get_product.return_value = None
    res = client.get("/api/products/999")
    assert res.status_code == 404


def test_update_product_success(client, mock_db):
    product = {"id": 1, "title": "新名稱", "summary": "摘要", "pet_id": None, "created_at": None, "updated_at": None}
    mock_db.get_product.return_value = product
    res = client.put("/api/products/1", json={"title": "新名稱", "summary": "摘要"})
    assert res.status_code == 200
    assert res.get_json()["title"] == "新名稱"
    mock_db.update_product.assert_called_once()


def test_delete_product_not_found_returns_404(client, mock_db):
    mock_db.get_product.return_value = None
    res = client.delete("/api/products/999")
    assert res.status_code == 404
