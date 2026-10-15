from datetime import datetime, timezone

from db import get_db


def create(product, buyer_id, price):
    doc = {"product_id": product["_id"], "seller_id": product["seller_id"], "buyer_id": buyer_id,
           "price": price, "status": "COMPLETED", "completed_at": datetime.now(timezone.utc)}
    return get_db().transactions.insert_one(doc).inserted_id


def get(transaction_id):
    return get_db().transactions.find_one({"_id": transaction_id})


def _join(local_user_field, as_name, hide):
    return [
        {"$lookup": {"from": "users", "localField": local_user_field, "foreignField": "_id", "as": as_name}},
        {"$unwind": {"path": "$" + as_name, "preserveNullAndEmptyArrays": True}},
        {"$project": {f"{as_name}.{f}": 0 for f in hide}},
    ]


_PRODUCT_AND_REVIEW = [
    {"$lookup": {"from": "products", "localField": "product_id", "foreignField": "_id", "as": "product"}},
    {"$unwind": "$product"},
    {"$lookup": {"from": "reviews", "localField": "_id", "foreignField": "transaction_id", "as": "review"}},
    {"$unwind": {"path": "$review", "preserveNullAndEmptyArrays": True}},
]
_HIDE = ("password_hash", "email", "phone", "registration_number")


def sold_by_seller(seller_id):
    pipeline = ([{"$match": {"seller_id": seller_id}}, {"$sort": {"completed_at": -1}}]
                + _PRODUCT_AND_REVIEW + _join("buyer_id", "buyer", _HIDE))
    return list(get_db().transactions.aggregate(pipeline))


def purchases_for_buyer(buyer_id):
    pipeline = ([{"$match": {"buyer_id": buyer_id}}, {"$sort": {"completed_at": -1}}]
                + _PRODUCT_AND_REVIEW + _join("seller_id", "seller", _HIDE))
    return list(get_db().transactions.aggregate(pipeline))
