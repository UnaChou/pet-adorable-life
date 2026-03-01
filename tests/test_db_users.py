"""Tests for db.py user CRUD functions."""
from unittest.mock import patch, MagicMock
import datetime


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


def test_create_user_returns_id():
    conn, cur = _make_conn(lastrowid=7)
    with patch("db.get_connection", return_value=conn):
        import db
        result = db.create_user("alice", "hashed_pw")
    assert result == 7
    call_sql = cur.execute.call_args[0][0]
    assert "INSERT INTO users" in call_sql


def test_get_user_by_username_returns_user():
    user_row = {"id": 1, "username": "alice", "password_hash": "hashed", "created_at": datetime.datetime.now()}
    conn, cur = _make_conn(fetchone=user_row)
    with patch("db.get_connection", return_value=conn):
        import db
        result = db.get_user_by_username("alice")
    assert result["username"] == "alice"


def test_get_user_by_username_returns_none_when_not_found():
    conn, cur = _make_conn(fetchone=None)
    with patch("db.get_connection", return_value=conn):
        import db
        result = db.get_user_by_username("nobody")
    assert result is None


def test_get_user_by_id_returns_user():
    user_row = {"id": 3, "username": "bob", "password_hash": "hashed", "created_at": datetime.datetime.now()}
    conn, cur = _make_conn(fetchone=user_row)
    with patch("db.get_connection", return_value=conn):
        import db
        result = db.get_user_by_id(3)
    assert result["id"] == 3


def test_get_user_by_id_returns_none_when_not_found():
    conn, cur = _make_conn(fetchone=None)
    with patch("db.get_connection", return_value=conn):
        import db
        result = db.get_user_by_id(999)
    assert result is None
