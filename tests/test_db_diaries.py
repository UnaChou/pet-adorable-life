"""Tests for db.py diary CRUD functions."""
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


def _diary_row(pet_id=None):
    return {
        "id": 1, "title": "快樂日", "describe_text": "玩耍", "main_emotion": "開心",
        "memo": "", "image_base64": "", "pet_id": pet_id,
        "created_at": datetime.datetime.now(), "updated_at": None,
    }


def test_get_all_diaries_no_filter():
    conn, cur = _make_conn(fetchall=[_diary_row()])
    with patch("db.get_connection", return_value=conn):
        import db
        result = db.get_all_diaries()
    assert len(result) == 1
    assert result[0]["main_emotion"] == "開心"


def test_get_all_diaries_pet_id_zero_uses_is_null():
    conn, cur = _make_conn(fetchall=[])
    with patch("db.get_connection", return_value=conn):
        import db
        db.get_all_diaries(pet_id=0)
    sql = cur.execute.call_args[0][0]
    assert "IS NULL" in sql


def test_get_all_diaries_specific_pet():
    conn, cur = _make_conn(fetchall=[])
    with patch("db.get_connection", return_value=conn):
        import db
        db.get_all_diaries(pet_id=3)
    sql, args = cur.execute.call_args[0]
    assert "pet_id = %s" in sql
    assert 3 in args


def test_add_diary_returns_id():
    conn, cur = _make_conn(lastrowid=7)
    with patch("db.get_connection", return_value=conn):
        import db
        result = db.add_diary("標題", "描述", "開心", "備註", "img_base64", pet_id=2)
    assert result == 7


def test_add_diary_with_no_pet():
    conn, cur = _make_conn(lastrowid=8)
    with patch("db.get_connection", return_value=conn):
        import db
        result = db.add_diary("T", "D", "E", "M")
    assert result == 8
    args = cur.execute.call_args[0][1]
    assert args[-1] is None  # pet_id=None stored as None


def test_get_diary_returns_dict():
    row = _diary_row(pet_id=1)
    conn, cur = _make_conn(fetchone=row)
    with patch("db.get_connection", return_value=conn):
        import db
        result = db.get_diary(1)
    assert result["title"] == "快樂日"
    assert result["pet_id"] == 1


def test_get_diary_not_found_returns_none():
    conn, cur = _make_conn(fetchone=None)
    with patch("db.get_connection", return_value=conn):
        import db
        result = db.get_diary(999)
    assert result is None


def test_remove_diaries_batch():
    conn, cur = _make_conn()
    with patch("db.get_connection", return_value=conn):
        import db
        db.remove_diaries([1, 2, 3])
    sql = cur.execute.call_args[0][0]
    assert "IN" in sql
    assert "pet_diaries" in sql


def test_remove_diaries_empty_list_no_op():
    conn, cur = _make_conn()
    with patch("db.get_connection", return_value=conn):
        import db
        db.remove_diaries([])
    cur.execute.assert_not_called()


def test_remove_pet_nullifies_references():
    conn, cur = _make_conn()
    with patch("db.get_connection", return_value=conn):
        import db
        db.remove_pet(3)
    calls = [c[0][0] for c in cur.execute.call_args_list]
    assert any("UPDATE products SET pet_id = NULL" in sql for sql in calls)
    assert any("UPDATE pet_diaries SET pet_id = NULL" in sql for sql in calls)
    assert any("DELETE FROM pets" in sql for sql in calls)
