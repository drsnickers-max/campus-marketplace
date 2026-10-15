import re
from datetime import datetime, timezone

from pymongo import ReturnDocument

from constants import AVAILABLE, SOLD, SORT_OPTIONS
from db import get_db

# Join the seller but strip private fields inside MongoDB itself.
_SELLER_STAGES = [
    {"$lookup": {"from": "users", "localField": "seller_id", "foreignField": "_id", "as": "seller"}},
    {"$unwind": "$seller"},
    {"$project": {"seller.password_hash": 0, "seller.email": 0,
                  "seller.phone": 0, "seller.registration_number": 0}},
]


def create_product(doc):
    now = datetime.now(timezone.utc)
    return get_db().products.insert_one({**doc, "created_at": now, "updated_at": now}).inserted_id


def get_product(product_id):
    return get_db().products.find_one({"_id": product_id})


def get_with_seller(product_id):
    rows = list(get_db().products.aggregate([{"$match": {"_id": product_id}}] + _SELLER_STAGES))
    return rows[0] if rows else None


def build_match(filters):
    """Build a query only from validated values (see services.validators.parse_filters)."""
    match = {"status": AVAILABLE}
    if filters.get("category"):
        match["category"] = filters["category"]
    if filters.get("condition"):
        match["condition"] = filters["condition"]
    price = {}
    if filters.get("min_price") is not None:
        price["$gte"] = filters["min_price"]
    if filters.get("max_price") is not None:
        price["$lte"] = filters["max_price"]
    if price:
        match["price"] = price
    words = filters.get("q", "").split()[:5]
    if words:
        # re.escape turns user text into a literal, so it can't be a regex attack
        match["$and"] = [
            {"$or": [{"title": {"$regex": re.escape(w), "$options": "i"}},
                     {"description": {"$regex": re.escape(w), "$options": "i"}}]}
            for w in words
        ]
    return match


def search(filters, page, per_page):
    db = get_db()
    match = build_match(filters)
    total = db.products.count_documents(match)
    pipeline = [
        {"$match": match},
        {"$sort": SORT_OPTIONS[filters["sort"]][1]},
        {"$skip": (page - 1) * per_page},
        {"$limit": per_page},
    ] + _SELLER_STAGES
    return list(db.products.aggregate(pipeline)), total


def list_by_seller(seller_id, status=None):
    query = {"seller_id": seller_id}
    if status:
        query["status"] = status
    return list(get_db().products.find(query).sort([("created_at", -1), ("_id", -1)]))


def update_product(product_id, seller_id, fields):
    """Filter includes seller_id AND status, so ownership is enforced inside the query."""
    res = get_db().products.update_one(
        {"_id": product_id, "seller_id": seller_id, "status": AVAILABLE},
        {"$set": {**fields, "updated_at": datetime.now(timezone.utc)}},
    )
    return res.matched_count


def mark_sold(product_id, seller_id):
    """Atomic: only one caller can flip AVAILABLE -> SOLD, even with double-clicks."""
    now = datetime.now(timezone.utc)
    return get_db().products.find_one_and_update(
        {"_id": product_id, "seller_id": seller_id, "status": AVAILABLE},
        {"$set": {"status": SOLD, "sold_at": now, "updated_at": now}},
        return_document=ReturnDocument.AFTER,
    )
