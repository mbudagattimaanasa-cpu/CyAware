import os
import tempfile
import pytest
from backend.app import create_app, database


@pytest.fixture
def app():
    """Create and configure a Flask application with an isolated temporary SQLite database."""
    db_fd, db_path = tempfile.mkstemp(suffix=".sqlite")
    os.close(db_fd)

    test_app = create_app("testing")
    test_app.config["DATABASE_PATH"] = db_path

    with test_app.app_context():
        database.init_db()
        yield test_app

    # Cleanup temporary database file after test
    try:
        os.unlink(db_path)
    except OSError:
        pass


@pytest.fixture
def client(app):
    """Test client for issuing requests."""
    return app.test_client()


@pytest.fixture
def runner(app):
    """Test CLI runner."""
    return app.test_cli_runner()
