import pytest
from app.db.connection import get_connection, init_db

@pytest.fixture
def db_conn(tmp_path):
    conn = get_connection(str(tmp_path / "test.db"))
    init_db(conn)
    yield conn
    conn.close()
