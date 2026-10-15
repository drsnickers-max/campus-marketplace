import mongomock
import pytest

from app import create_app


@pytest.fixture
def app(tmp_path):
    return create_app(
        test_config={"TESTING": True, "WTF_CSRF_ENABLED": False, "RATELIMIT_ENABLED": False,
                     "MONGO_DB_NAME": "test_db", "UPLOAD_FOLDER": str(tmp_path / "uploads"),
                     "BCRYPT_ROUNDS": 4, "SECRET_KEY": "test-secret", "PER_PAGE": 3},
        mongo_client=mongomock.MongoClient())


@pytest.fixture
def client(app):
    return app.test_client()
