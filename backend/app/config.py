import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")


class Config:
    """Base configuration settings."""
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-cyaware-college-project-2026")
    INSTANCE_DIR = BASE_DIR / "instance"
    DATABASE_PATH = os.environ.get("DATABASE_PATH", str(INSTANCE_DIR / "cyaware.sqlite"))

    # Session and Cookie security
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = os.environ.get("SESSION_COOKIE_SAMESITE", "Lax")
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "False").lower() in ("true", "1")
    PERMANENT_SESSION_LIFETIME = 86400  # 24 hours

    # CSRF Protection
    CSRF_ENABLED = True

    # Upload constraints
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10 MB absolute max payload
    MAX_FILE_UPLOAD_BYTES = 2 * 1024 * 1024  # 2 MB for TXT/CSV
    MAX_IMAGE_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB for screenshot OCR
    MAX_CSV_ROWS = 500

    TESTING = False
    DEBUG = False


class DevelopmentConfig(Config):
    """Development environment configuration."""
    DEBUG = True


class TestingConfig(Config):
    """Testing configuration with in-memory SQLite."""
    TESTING = True
    DEBUG = True
    DATABASE_PATH = ":memory:"
    SECRET_KEY = "test-secret-key"


class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    SESSION_COOKIE_SECURE = True


config_by_name = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}

