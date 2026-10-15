from datetime import datetime, timezone

from db import get_db


def create(transaction, rating, comment):
    doc = {"transaction_id": transaction["_id"], "product_id": transaction["product_id"],
           "buyer_id": transaction["buyer_id"], "seller_id": transaction["seller_id"],
           "rating": rating, "comment": comment, "created_at": datetime.now(timezone.utc)}
    return get_db().reviews.insert_one(doc).inserted_id


def recalculate_seller_rating(seller_id):
    """Recompute from the reviews collection ($group) so the average is always exact."""
    db = get_db()
    rows = list(db.reviews.aggregate([
        {"$match": {"seller_id": seller_id}},
        {"$group": {"_id": "$seller_id", "avg": {"$avg": "$rating"}, "count": {"$sum": 1}}},
    ]))
    avg = round(float(rows[0]["avg"]), 2) if rows else 0.0
    count = int(rows[0]["count"]) if rows else 0
    db.users.update_one({"_id": seller_id}, {"$set": {"avg_rating": avg, "review_count": count}})
    return avg, count


def for_seller(seller_id, limit=20):
    return list(get_db().reviews.aggregate([
        {"$match": {"seller_id": seller_id}},
        {"$sort": {"created_at": -1}},
        {"$limit": limit},
        {"$lookup": {"from": "users", "localField": "buyer_id", "foreignField": "_id", "as": "buyer"}},
        {"$unwind": {"path": "$buyer", "preserveNullAndEmptyArrays": True}},
        {"$project": {"buyer.password_hash": 0, "buyer.email": 0, "buyer.phone": 0,
                      "buyer.registration_number": 0}},
    ]))
