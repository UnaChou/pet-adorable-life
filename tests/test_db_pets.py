import pytest
from unittest.mock import patch, MagicMock


def _make_conn_mock(fetchone_val=None, fetchall_val=None, lastrowid=1):
    mock_cur = MagicMock()
    mock_cur.fetchone.return_value = fetchone_val
    mock_cur.fetchall.return_value = fetchall_val or []
    mock_cur.lastrowid = lastrowid
    mock_cur.__enter__ = MagicMock(return_value=mock_cur)
    mock_cur.__exit__ = MagicMock(return_value=False)

    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cur
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    return mock_conn, mock_cur


def test_add_pet_returns_id():
    mock_conn, mock_cur = _make_conn_mock(lastrowid=5)
    with patch("db.get_connection", return_value=mock_conn):
        import db
        result = db.add_pet("小黑", "柴犬", "2020-01-15", "")
    assert result == 5


def test_get_pet_returns_none_when_not_found():
    mock_conn, mock_cur = _make_conn_mock(fetchone_val=None)
    with patch("db.get_connection", return_value=mock_conn):
        import db
        result = db.get_pet(999)
    assert result is None


def test_get_pet_returns_dict():
    import datetime
    row = {
        "id": 1, "name": "小黑", "breed": "柴犬",
        "birthday": datetime.date(2020, 1, 15),
        "photo_base64": "", "created_at": datetime.datetime.now(), "updated_at": None
    }
    mock_conn, mock_cur = _make_conn_mock(fetchone_val=row)
    with patch("db.get_connection", return_value=mock_conn):
        import db
        result = db.get_pet(1)
    assert result["name"] == "小黑"
    assert result["birthday"] == "2020-01-15"


def test_get_all_products_accepts_pet_id_filter():
    mock_conn, mock_cur = _make_conn_mock(fetchall_val=[])
    with patch("db.get_connection", return_value=mock_conn):
        import db
        db.get_all_products(pet_id=2)
    sql = mock_cur.execute.call_args[0][0]
    assert "pet_id" in sql


def test_add_product_accepts_pet_id():
    mock_conn, mock_cur = _make_conn_mock(lastrowid=3)
    with patch("db.get_connection", return_value=mock_conn):
        import db
        db.add_product("飼料", "描述", pet_id=1)
    call_args = mock_cur.execute.call_args[0]
    assert 1 in call_args[1]


def test_get_all_pets_returns_empty_list():
    mock_conn, mock_cur = _make_conn_mock(fetchall_val=[])
    with patch("db.get_connection", return_value=mock_conn):
        import db
        result = db.get_all_pets()
    assert result == []


def test_get_all_pets_returns_formatted_list():
    import datetime
    row = {
        "id": 1, "name": "小黑", "breed": "柴犬",
        "birthday": datetime.date(2020, 1, 15),
        "photo_base64": "abc", "created_at": datetime.datetime.now(), "updated_at": None,
    }
    mock_conn, mock_cur = _make_conn_mock(fetchall_val=[row])
    with patch("db.get_connection", return_value=mock_conn):
        import db
        result = db.get_all_pets()
    assert len(result) == 1
    assert result[0]["name"] == "小黑"
    assert result[0]["birthday"] == "2020-01-15"


def test_update_pet_with_photo_updates_photo_field():
    mock_conn, mock_cur = _make_conn_mock()
    with patch("db.get_connection", return_value=mock_conn):
        import db
        db.update_pet(1, "小黑", "柴犬", "2020-01-01", photo_base64="base64data")
    sql = mock_cur.execute.call_args[0][0]
    assert "photo_base64" in sql


def test_update_pet_without_photo_excludes_photo_field():
    mock_conn, mock_cur = _make_conn_mock()
    with patch("db.get_connection", return_value=mock_conn):
        import db
        db.update_pet(1, "小黑", "柴犬", "2020-01-01", photo_base64=None)
    sql = mock_cur.execute.call_args[0][0]
    assert "photo_base64" not in sql
