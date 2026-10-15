from datetime import datetime, timezone

from db import get_db
from services.validators import to_object_id

PUBLIC_FIELDS = ("_id", "full_name", "academic_year", "avg_rating", "review_count",
                 "profile_picture", "created_at")


def create_user(data):
    doc = {**data, "avg_rating": 0.0, "review_count": 0, "created_at": datetime.now(timezone.utc)}
    return get_db().users.insert_one(doc).inserted_id


def get_by_id(user_id):
    """Never returns the password hash."""
    oid = to_object_id(user_id)
    return get_db().users.find_one({"_id": oid}, {"password_hash": 0}) if oid else None


def get_by_email(email):
    """Includes the hash. Only the login route should call this."""
    return get_db().users.find_one({"email": email})


def update_profile(user_id, fields):
    get_db().users.update_one({"_id": user_id}, {"$set": fields})


def public_view(user):
    return {k: user.get(k) for k in PUBLIC_FIELDS} if user else None
