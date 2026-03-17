import pytest
import pymysql
from unittest.mock import patch, MagicMock


def test_get_db_config_returns_required_keys():
    import db
    config = db._get_db_config()
    assert "host" in config
    assert "database" in config
    assert "user" in config
    assert "charset" in config


def test_get_connection_commits_on_success():
    import db
    mock_conn = MagicMock()
    with patch("pymysql.connect", return_value=mock_conn):
        with db.get_connection() as conn:
            assert conn is mock_conn
    mock_conn.commit.assert_called_once()
    mock_conn.close.assert_called_once()


def test_get_connection_rolls_back_on_exception():
    import db
    mock_conn = MagicMock()
    with patch("pymysql.connect", return_value=mock_conn):
        with pytest.raises(RuntimeError):
            with db.get_connection() as conn:
                raise RuntimeError("test error")
    mock_conn.rollback.assert_called_once()
    mock_conn.close.assert_called_once()


def test_init_db_raises_on_non_duplicate_column_error():
    import db
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_cur.__enter__ = MagicMock(return_value=mock_cur)
    mock_cur.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value = mock_cur

    error = pymysql.err.OperationalError(1005, "some other db error")
    # First call (CREATE TABLE products) succeeds; second (ALTER TABLE) raises
    mock_cur.execute.side_effect = [None, error]

    with patch("db.get_connection", return_value=mock_conn):
        with pytest.raises(pymysql.err.OperationalError):
            db.init_db()


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
