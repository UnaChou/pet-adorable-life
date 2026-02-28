"""Tests for db.py product CRUD functions."""
import datetime
from unittest.mock import patch, MagicMock


def _make_conn(fetchone=None, fetchall=None, lastrowid=1):
    cur = MagicMock()
    cur.fetchone.return_value = fetchone
    cur.fetchall.return_value = fetchall or []
    cur.lastrowid = lastrowid
    cur.__enter__ = MagicMock(return_value=cur)
    cur.__exit__ = MagicMock(return_value=False)
    conn = MagicMock()
    conn.cursor.return_value = cur
    conn.__enter__ = MagicMock(return_value=conn)
    conn.__exit__ = MagicMock(return_value=False)
    return conn, cur


def test_get_all_products_no_filter():
    conn, cur = _make_conn(fetchall=[])
    with patch("db.get_connection", return_value=conn):
        import db
        result = db.get_all_products()
    sql = cur.execute.call_args[0][0]
    # no pet_id filter applied (pet_id may appear in the SELECT column list)
    assert "pet_id is null" not in sql.lower()
    assert "pet_id = " not in sql.lower()


def test_get_all_products_pet_id_zero_uses_is_null():
    conn, cur = _make_conn(fetchall=[])
    with patch("db.get_connection", return_value=conn):
        import db
        db.get_all_products(pet_id=0)
    sql = cur.execute.call_args[0][0]
    assert "IS NULL" in sql


def test_get_all_products_returns_list():
    row = {"id": 1, "title": "飼料", "summary": "好", "pet_id": None, "created_at": datetime.datetime.now(), "updated_at": None}
    conn, cur = _make_conn(fetchall=[row])
    with patch("db.get_connection", return_value=conn):
        import db
        result = db.get_all_products()
    assert len(result) == 1
    assert result[0]["title"] == "飼料"


def test_get_product_returns_dict():
    row = {"id": 2, "title": "玩具", "summary": "好玩", "pet_id": 1, "created_at": datetime.datetime.now(), "updated_at": None}
    conn, cur = _make_conn(fetchone=row)
    with patch("db.get_connection", return_value=conn):
        import db
        result = db.get_product(2)
    assert result["title"] == "玩具"
    assert result["pet_id"] == 1


def test_get_product_not_found_returns_none():
    conn, cur = _make_conn(fetchone=None)
    with patch("db.get_connection", return_value=conn):
        import db
        result = db.get_product(999)
    assert result is None


def test_update_product_executes_sql():
    conn, cur = _make_conn()
    with patch("db.get_connection", return_value=conn):
        import db
        db.update_product(1, "新名稱", "新摘要", pet_id=2)
    sql, args = cur.execute.call_args[0]
    assert "UPDATE products" in sql
    assert "新名稱" in args
    assert 2 in args


def test_remove_product_executes_delete():
    conn, cur = _make_conn()
    with patch("db.get_connection", return_value=conn):
        import db
        db.remove_product(5)
    sql = cur.execute.call_args[0][0]
    assert "DELETE FROM products" in sql


def test_remove_products_batch():
    conn, cur = _make_conn()
    with patch("db.get_connection", return_value=conn):
        import db
        db.remove_products([1, 2, 3])
    sql = cur.execute.call_args[0][0]
    assert "IN" in sql


def test_remove_products_empty_list_no_op():
    conn, cur = _make_conn()
    with patch("db.get_connection", return_value=conn):
        import db
        db.remove_products([])
    cur.execute.assert_not_called()
