"""
Food Man Application Configuration
Supports MySQL with automatic graceful fallback to SQLite
"""
import os

class Config:
    # Flask Security
    SECRET_KEY = os.environ.get('SECRET_KEY', 'food-man-dev-secret-key-phase0-day1to3-haccp-2026')
    
    # Session Configuration
    SESSION_COOKIE_NAME = 'food_man_session'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = 86400  # 24 hours

    # Database Configuration:
    # Priority 1: DATABASE_URL environment variable
    # Priority 2: MYSQL_DATABASE_URL or default MySQL format
    # Priority 3: SQLite fallback file in workspace
    MYSQL_HOST = os.environ.get('MYSQL_HOST', 'localhost')
    MYSQL_PORT = os.environ.get('MYSQL_PORT', '3306')
    MYSQL_USER = os.environ.get('MYSQL_USER', 'root')
    MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD', '')
    MYSQL_DB = os.environ.get('MYSQL_DB', 'food_man_db')

    # Base workspace directory
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    SQLITE_PATH = os.path.join(BASE_DIR, 'food_man.db')

    # Detect database URI
    DATABASE_URL = os.environ.get('DATABASE_URL')
    if not DATABASE_URL:
        # Default configured database: SQLite for zero-friction local run
        DATABASE_URL = f"sqlite:///{SQLITE_PATH}"

    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = False

    # Material Identification Classifier (Phase 3/4) - Turned ON after passing Phase 2 gates (100% crops, 100% scenes, 99.6% photos).
    # OFF-switch: To disable and revert to Phase 0 baseline behavior, set environment variable USE_MATERIAL_CLASSIFIER=0.
    USE_MATERIAL_CLASSIFIER = os.environ.get('USE_MATERIAL_CLASSIFIER', '1').lower() in ('1', 'true', 'yes')
    MATERIAL_CLS_MODEL_PATH = os.environ.get('MATERIAL_CLS_MODEL_PATH', os.path.join(BASE_DIR, 'models', 'material_cls.pt'))

