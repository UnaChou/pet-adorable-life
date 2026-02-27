import pytest
from unittest.mock import patch, MagicMock, call


def test_init_db_creates_pets_table():
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_cur.__enter__ = MagicMock(return_value=mock_cur)
    mock_cur.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value = mock_cur

    with patch("db.get_connection", return_value=mock_conn):
        import db
        db.init_db()

    sql_calls = " ".join(str(c) for c in mock_cur.execute.call_args_list)
    assert "pets" in sql_calls.lower()
    assert "pet_id" in sql_calls.lower()
