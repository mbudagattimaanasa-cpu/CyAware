import sqlite3
from pathlib import Path
from flask import g, current_app


def get_db():
    """Retrieve or create the database connection for the current request context."""
    if "db" not in g:
        db_path = current_app.config["DATABASE_PATH"]
        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        g.db = sqlite3.connect(db_path)
        g.db.row_factory = sqlite3.Row
        # Enforce foreign key constraints on every connection
        g.db.execute("PRAGMA foreign_keys = ON;")

    return g.db


def close_db(e=None):
    """Close the current request's database connection if open."""
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(app=None):
    """Initialize the database schema from schema.sql."""
    target_app = app or current_app
    with target_app.app_context():
        db = get_db()
        schema_path = Path(__file__).resolve().parent / "schema.sql"
        with open(schema_path, "r", encoding="utf-8") as f:
            db.executescript(f.read())
        db.commit()


def query_db(query, args=(), one=False):
    """Execute a parameterized SELECT query and return dict-like rows."""
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv


def execute_db(query, args=(), commit=True):
    """Execute a parameterized INSERT/UPDATE/DELETE query and return the last row ID."""
    db = get_db()
    cur = db.execute(query, args)
    if commit:
        db.commit()
    last_id = cur.lastrowid
    cur.close()
    return last_id


def init_app(app):
    """Register database teardown and CLI commands with the Flask application."""
    app.teardown_appcontext(close_db)

    @app.cli.command("init-db")
    def init_db_command():
        """Clear existing data and create new tables."""
        init_db(app)
        print("Initialized the database successfully.")
