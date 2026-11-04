import os
from backend.app import create_app, database

env = os.environ.get("FLASK_ENV", "development")
app = create_app(env)

if __name__ == "__main__":
    # Ensure database is initialized before starting dev server
    with app.app_context():
        database.init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="127.0.0.1", port=port, debug=app.config["DEBUG"])

