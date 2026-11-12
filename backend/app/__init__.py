import os
from datetime import datetime, timezone
from flask import Flask, jsonify, send_from_directory, abort, session, redirect
from werkzeug.exceptions import NotFound
from .config import config_by_name
from . import database
from .routes.auth import auth_bp
from .routes.analyze import analyze_bp
from .routes.analyses import analyses_bp
from .routes.dashboard import dashboard_bp
from .routes.user import user_bp
from .commands import register_commands
from .middleware import validate_csrf


def create_app(config_name=None):
    """Application factory for CyAware Flask backend."""
    if config_name is None:
        config_name = os.environ.get("FLASK_ENV", "development").lower()

    app = Flask(__name__, instance_relative_config=True)
    config_class = config_by_name.get(config_name, config_by_name["default"])
    app.config.from_object(config_class)

    # Ensure instance directory exists
    try:
        os.makedirs(app.instance_path, exist_ok=True)
    except OSError:
        pass

    # Initialize database and CLI commands
    database.init_app(app)
    register_commands(app)

    # Register API Blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(analyze_bp)
    app.register_blueprint(analyses_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(user_bp)

    # CSRF Protection for state-changing requests on authenticated sessions
    @app.before_request
    def check_csrf():
        return validate_csrf()

    # Global Security Headers
    @app.after_request
    def set_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Content-Security-Policy"] = "default-src 'self'"
        return response

    # Health & Status Endpoint
    @app.route("/api/health", methods=["GET"])
    def health_check():
        db_status = "connected"
        try:
            db = database.get_db()
            db.execute("SELECT 1").fetchone()
        except Exception as e:
            db_status = f"error: {str(e)}"

        return jsonify({
            "success": True,
            "data": {
                "status": "healthy" if db_status == "connected" else "degraded",
                "database": db_status,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "version": "1.0.0-stage2"
            },
            "message": "CyAware Backend API is operational."
        }), 200

    # Frontend Static Hosting (Stage 3.1)
    frontend_dir = os.path.abspath(os.path.join(app.root_path, "..", "..", "frontend"))

    @app.route("/", methods=["GET"])
    def serve_index():
        return send_from_directory(frontend_dir, "index.html")

    # Protected Admin Interface Route (Stage 3.5 Access Control)
    @app.route("/admin.html", methods=["GET"])
    @app.route("/admin", methods=["GET"])
    def serve_admin_page():
        user_id = session.get("user_id")
        if not user_id:
            return redirect("/login.html")

        user = database.query_db(
            "SELECT id, role, is_active FROM users WHERE id = ?",
            (user_id,),
            one=True
        )
        if not user or user["is_active"] != 1:
            session.clear()
            return redirect("/login.html")

        if user["role"] != "admin":
            abort(403)

        return send_from_directory(frontend_dir, "admin.html")

    @app.route("/<path:filename>", methods=["GET"])
    def serve_frontend_file(filename):
        # Do not serve frontend static files for /api/... routes
        if filename == "api" or filename.startswith("api/"):
            abort(404)
        if filename in ("admin.html", "admin"):
            return serve_admin_page()
        try:
            return send_from_directory(frontend_dir, filename)
        except NotFound:
            # Check for extensionless HTML route e.g. /login -> login.html
            if os.path.isfile(os.path.join(frontend_dir, filename + ".html")):
                try:
                    return send_from_directory(frontend_dir, filename + ".html")
                except NotFound:
                    pass
            abort(404)

    # Standard JSON Error Handlers
    @app.errorhandler(400)
    def bad_request(error):
        return jsonify({
            "success": False,
            "error": {
                "code": "BAD_REQUEST",
                "message": getattr(error, "description", "Bad Request")
            }
        }), 400

    @app.errorhandler(401)
    def unauthorized(error):
        return jsonify({
            "success": False,
            "error": {
                "code": "UNAUTHENTICATED",
                "message": getattr(error, "description", "Authentication required.")
            }
        }), 401

    @app.errorhandler(403)
    def forbidden(error):
        return jsonify({
            "success": False,
            "error": {
                "code": "FORBIDDEN",
                "message": getattr(error, "description", "Access denied.")
            }
        }), 403

    @app.errorhandler(404)
    def not_found(error):
        return jsonify({
            "success": False,
            "error": {
                "code": "NOT_FOUND",
                "message": getattr(error, "description", "The requested resource was not found.")
            }
        }), 404

    @app.errorhandler(405)
    def method_not_allowed(error):
        return jsonify({
            "success": False,
            "error": {
                "code": "METHOD_NOT_ALLOWED",
                "message": "The HTTP method is not allowed for this endpoint."
            }
        }), 405

    @app.errorhandler(413)
    def request_entity_too_large(error):
        return jsonify({
            "success": False,
            "error": {
                "code": "PAYLOAD_TOO_LARGE",
                "message": "Uploaded content exceeds the maximum allowed limit."
            }
        }), 413

    @app.errorhandler(500)
    def internal_server_error(error):
        return jsonify({
            "success": False,
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An internal server error occurred."
            }
        }), 500

    return app
