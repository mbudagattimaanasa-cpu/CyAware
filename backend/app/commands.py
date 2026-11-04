import click
from werkzeug.security import generate_password_hash
from backend.app.database import query_db, execute_db


def register_commands(app):
    """Register custom Flask CLI commands."""

    @app.cli.command("create-admin")
    @click.option("--username", prompt=True, help="Admin username")
    @click.option("--email", prompt=True, help="Admin email address")
    @click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True, help="Admin password")
    def create_admin_command(username, email, password):
        """Securely create or promote an administrative user account."""
        username = username.strip()
        email = email.strip().lower()

        if len(password) < 8 or not any(c.isalpha() for c in password) or not any(c.isdigit() for c in password):
            click.echo("Error: Password must be at least 8 characters long and contain both letters and numbers.")
            return

        existing = query_db(
            "SELECT id, username, email, role FROM users WHERE LOWER(username) = LOWER(?) OR LOWER(email) = LOWER(?)",
            (username, email),
            one=True
        )

        password_hash = generate_password_hash(password)

        if existing:
            # Promote existing user to admin
            execute_db(
                "UPDATE users SET role = 'admin', password_hash = ?, is_active = 1 WHERE id = ?",
                (password_hash, existing["id"])
            )
            execute_db(
                "INSERT INTO audit_logs (user_id, action, details) VALUES (?, 'ADMIN_PROMOTED', 'User promoted to admin via CLI')",
                (existing["id"],)
            )
            click.echo(f"User '{username}' was updated to Admin role successfully.")
        else:
            user_id = execute_db(
                """INSERT INTO users (username, email, password_hash, role, is_active)
                   VALUES (?, ?, ?, 'admin', 1)""",
                (username, email, password_hash)
            )
            execute_db(
                "INSERT INTO audit_logs (user_id, action, details) VALUES (?, 'ADMIN_CREATED', 'Admin account created via CLI')",
                (user_id,)
            )
            click.echo(f"Admin user '{username}' created successfully (ID: {user_id}).")

