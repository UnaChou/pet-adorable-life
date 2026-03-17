"""Shared test helpers for db mock connection setup."""
from unittest.mock import MagicMock


def make_conn(fetchone=None, fetchall=None, lastrowid=1):
    """Build a mock PyMySQL connection + cursor pair for db unit tests."""
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
