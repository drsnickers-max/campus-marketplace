import logging
from pymongo import ASCENDING, DESCENDING, MongoClient

from constants import AVAILABLE, CATEGORIES, CONDITIONS, SOLD

logger = logging.getLogger(__name__)
_client = None
_db = None


def init_db(app, client=None):
    """Connect, apply schema validation, create indexes. `client` is for tests."""
    global _client, _db
    _client = client or MongoClient(app.config["MONGO_URI"], serverSelectionTimeoutMS=5000)
    _db = _client[app.config["MONGO_DB_NAME"]]
    _client.admin.command("ping")  # fail fast if MongoDB is unreachable
    apply_schema_validation(_db)
    create_indexes(_db)


def get_db():
    if _db is None:
        raise RuntimeError("Database not initialised. Call init_db first.")
    return _db


def _schema(required, properties):
    return {"$jsonSchema": {"bsonType": "object", "required": required, "properties": properties}}


_INT = ["int", "long"]
_NUM = ["double", "int", "long"]

# Server-side schema validation: MongoDB itself rejects malformed documents.
VALIDATORS = {
    "users": _schema(
        ["full_name", "email", "registration_number", "phone", "academic_year",
         "password_hash", "avg_rating", "review_count", "created_at"],
        {"full_name": {"bsonType": "string"}, "email": {"bsonType": "string"},
         "registration_number": {"bsonType": "string"}, "phone": {"bsonType": "string"},
         "academic_year": {"bsonType": _INT, "minimum": 1, "maximum": 6},
         "avg_rating": {"bsonType": _NUM, "minimum": 0, "maximum": 5},
         "review_count": {"bsonType": _INT, "minimum": 0}},
    ),
    "products": _schema(
        ["title", "description", "price", "category", "condition", "images",
         "seller_id", "status", "created_at"],
        {"title": {"bsonType": "string"}, "description": {"bsonType": "string"},
         "price": {"bsonType": _INT, "minimum": 1},
         "category": {"enum": CATEGORIES}, "condition": {"enum": CONDITIONS},
         "images": {"bsonType": "array"}, "seller_id": {"bsonType": "objectId"},
         "status": {"enum": [AVAILABLE, SOLD]}},
    ),
    "transactions": _schema(
        ["product_id", "seller_id", "price", "status", "completed_at"],
        {"product_id": {"bsonType": "objectId"}, "seller_id": {"bsonType": "objectId"},
         "price": {"bsonType": _INT, "minimum": 1}, "status": {"enum": ["COMPLETED"]}},
    ),
    "reviews": _schema(
        ["transaction_id", "buyer_id", "seller_id", "rating", "created_at"],
        {"rating": {"bsonType": "int", "minimum": 1, "maximum": 5},
         "transaction_id": {"bsonType": "objectId"}},
    ),
    "inquiries": _schema(
        ["product_id", "buyer_id", "seller_id", "message", "created_at"],
        {"message": {"bsonType": "string"}, "product_id": {"bsonType": "objectId"}},
    ),
}


def apply_schema_validation(db):
    existing = set(db.list_collection_names())
    for name, validator in VALIDATORS.items():
        try:
            if name in existing:
                db.command("collMod", name, validator=validator,
                           validationLevel="strict", validationAction="error")
            else:
                db.create_collection(name, validator=validator)
        except Exception as exc:  # app still works; validation is defence in depth
            logger.warning("Could not apply schema validation to %s: %s", name, exc)


def create_indexes(db):
    # Uniqueness is enforced by the database, not just by Python checks
    db.users.create_index([("email", ASCENDING)], unique=True)
    db.users.create_index([("registration_number", ASCENDING)], unique=True)

    db.products.create_index([("status", ASCENDING), ("created_at", DESCENDING)])
    db.products.create_index([("status", ASCENDING), ("category", ASCENDING)])
    db.products.create_index([("status", ASCENDING), ("price", ASCENDING)])
    db.products.create_index([("seller_id", ASCENDING), ("status", ASCENDING)])

    # A product can be sold once; one review per transaction
    db.transactions.create_index([("product_id", ASCENDING)], unique=True)
    db.transactions.create_index([("seller_id", ASCENDING), ("completed_at", DESCENDING)])
    db.transactions.create_index([("buyer_id", ASCENDING), ("completed_at", DESCENDING)])
    db.reviews.create_index([("transaction_id", ASCENDING)], unique=True)
    db.reviews.create_index([("seller_id", ASCENDING), ("created_at", DESCENDING)])

    # One inquiry per buyer per product (stops spam)
    db.inquiries.create_index([("product_id", ASCENDING), ("buyer_id", ASCENDING)], unique=True)
    db.inquiries.create_index([("seller_id", ASCENDING), ("created_at", DESCENDING)])
    db.inquiries.create_index([("buyer_id", ASCENDING), ("created_at", DESCENDING)])
