from datetime import datetime, timezone

from db import get_db

_PRODUCT = [
    {"$lookup": {"from": "products", "localField": "product_id", "foreignField": "_id", "as": "product"}},
    {"$unwind": "$product"},
]


def create(product, buyer_id, message):
    doc = {"product_id": product["_id"], "seller_id": product["seller_id"], "buyer_id": buyer_id,
           "message": message, "created_at": datetime.now(timezone.utc)}
    return get_db().inquiries.insert_one(doc).inserted_id  # unique index blocks duplicates


def get(inquiry_id):
    return get_db().inquiries.find_one({"_id": inquiry_id})


def get_for_buyer(product_id, buyer_id):
    return get_db().inquiries.find_one({"product_id": product_id, "buyer_id": buyer_id})


def received(seller_id):
    """Seller sees the buyer's name, email and phone: the buyer chose to contact them."""
    return list(get_db().inquiries.aggregate(
        [{"$match": {"seller_id": seller_id}}, {"$sort": {"created_at": -1}}] + _PRODUCT + [
            {"$lookup": {"from": "users", "localField": "buyer_id", "foreignField": "_id", "as": "buyer"}},
            {"$unwind": "$buyer"},
            {"$project": {"buyer.password_hash": 0, "buyer.registration_number": 0}},
        ]))


def sent(buyer_id):
    rows = list(get_db().inquiries.aggregate(
        [{"$match": {"buyer_id": buyer_id}}, {"$sort": {"created_at": -1}}] + _PRODUCT + [
            {"$lookup": {"from": "users", "localField": "seller_id", "foreignField": "_id", "as": "seller"}},
            {"$unwind": "$seller"},
            {"$project": {"seller.password_hash": 0, "seller.registration_number": 0, "seller.email": 0}},
        ]))
    for row in rows:  # phone only if the seller explicitly shared it in their reply
        if not row.get("share_phone"):
            row["seller"].pop("phone", None)
    return rows


def set_reply(inquiry_id, seller_id, reply, share_phone):
    res = get_db().inquiries.update_one(
        {"_id": inquiry_id, "seller_id": seller_id},
        {"$set": {"reply": reply, "share_phone": share_phone, "replied_at": datetime.now(timezone.utc)}})
    return res.matched_count


def inquirers_for_product(product_id):
    rows = get_db().inquiries.aggregate([
        {"$match": {"product_id": product_id}},
        {"$lookup": {"from": "users", "localField": "buyer_id", "foreignField": "_id", "as": "buyer"}},
        {"$unwind": "$buyer"},
        {"$project": {"buyer_id": 1, "buyer_name": "$buyer.full_name"}},
    ])
    return list(rows)
