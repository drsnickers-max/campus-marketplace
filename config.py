import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()
BASE_DIR = os.path.abspath(os.path.dirname(__file__))


def _flag(name, default="0"):
    return os.environ.get(name, default).strip().lower() in ("1", "true", "yes")


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-insecure-key")
    MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
    MONGO_DB_NAME = os.environ.get("MONGO_DB_NAME", "campus_marketplace")

    # Sessions / cookies
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _flag("SESSION_COOKIE_SECURE")  # set 1 on HTTPS
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    WTF_CSRF_TIME_LIMIT = 7200

    # Limits
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024      # whole request
    MAX_IMAGE_BYTES = 5 * 1024 * 1024          # per image
    MAX_IMAGES = 5
    PER_PAGE = 12
    RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")
    BCRYPT_ROUNDS = 12

    # Access rules
    ALLOWED_EMAIL_DOMAINS = [
        d.strip().lower() for d in os.environ.get("ALLOWED_EMAIL_DOMAINS", "").split(",") if d.strip()
    ]
    REQUIRE_LOGIN_TO_BROWSE = _flag("REQUIRE_LOGIN_TO_BROWSE")

    # Images: Cloudinary if all three are set, otherwise local folder
    CLOUDINARY_CLOUD_NAME = os.environ.get("CLOUDINARY_CLOUD_NAME", "")
    CLOUDINARY_API_KEY = os.environ.get("CLOUDINARY_API_KEY", "")
    CLOUDINARY_API_SECRET = os.environ.get("CLOUDINARY_API_SECRET", "")
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
