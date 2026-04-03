from datetime import datetime


def test_calendar_items_happy_path(authed_client, mock_db):
    """Happy path — products and diaries in the requested month are returned."""
    mock_db.get_all_products.return_value = [
        {"id": 1, "title": "貓飼料", "created_at": datetime(2026, 4, 10, 9, 0, 0)},
        {"id": 2, "title": "狗玩具", "created_at": datetime(2026, 3, 5, 8, 0, 0)},  # different month
    ]
    mock_db.get_all_diaries.return_value = [
        {"id": 10, "title": "Mochi 日記", "created_at": datetime(2026, 4, 15, 12, 0, 0)},
    ]

    res = authed_client.get("/api/calendar-items?year=2026&month=4")

    assert res.status_code == 200
    data = res.get_json()
    assert "items" in data
    items = data["items"]
    assert len(items) == 2

    product_item = next(i for i in items if i["type"] == "product")
    assert product_item["id"] == 1
    assert product_item["title"] == "貓飼料"
    assert product_item["date"] == "2026-04-10"

    diary_item = next(i for i in items if i["type"] == "diary")
    assert diary_item["id"] == 10
    assert diary_item["title"] == "Mochi 日記"
    assert diary_item["date"] == "2026-04-15"


def test_calendar_items_empty_month(authed_client, mock_db):
    """Empty month — returns items=[] when no records fall in the requested month."""
    mock_db.get_all_products.return_value = [
        {"id": 1, "title": "貓飼料", "created_at": datetime(2026, 3, 10, 9, 0, 0)},
    ]
    mock_db.get_all_diaries.return_value = [
        {"id": 10, "title": "Mochi 日記", "created_at": datetime(2026, 3, 15, 12, 0, 0)},
    ]

    res = authed_client.get("/api/calendar-items?year=2026&month=4")

    assert res.status_code == 200
    assert res.get_json() == {"items": []}


def test_calendar_items_missing_year(authed_client, mock_db):
    """Missing year param — returns 400."""
    res = authed_client.get("/api/calendar-items?month=4")
    assert res.status_code == 400


def test_calendar_items_missing_month(authed_client, mock_db):
    """Missing month param — returns 400."""
    res = authed_client.get("/api/calendar-items?year=2026")
    assert res.status_code == 400


def test_calendar_items_invalid_month(authed_client, mock_db):
    """Invalid month (13) — returns 400."""
    res = authed_client.get("/api/calendar-items?year=2026&month=13")
    assert res.status_code == 400


def test_calendar_items_unauthenticated(client, mock_db):
    """Unauthenticated request — returns 401."""
    res = client.get("/api/calendar-items?year=2026&month=4")
    assert res.status_code == 401
