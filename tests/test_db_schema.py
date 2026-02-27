import pytest
from unittest.mock import patch, MagicMock


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

    all_sql = [str(c.args[0]) if c.args else "" for c in mock_cur.execute.call_args_list]

    # Verify CREATE TABLE IF NOT EXISTS pets was called
    assert any("CREATE TABLE IF NOT EXISTS pets" in sql for sql in all_sql), \
        "Expected CREATE TABLE IF NOT EXISTS pets in SQL calls"

    # Verify ALTER TABLE products ADD COLUMN pet_id was called
    assert any("ALTER TABLE products ADD COLUMN pet_id" in sql for sql in all_sql), \
        "Expected ALTER TABLE products ADD COLUMN pet_id in SQL calls"

    # Verify ALTER TABLE pet_diaries ADD COLUMN pet_id was called
    assert any("ALTER TABLE pet_diaries ADD COLUMN pet_id" in sql for sql in all_sql), \
        "Expected ALTER TABLE pet_diaries ADD COLUMN pet_id in SQL calls"
