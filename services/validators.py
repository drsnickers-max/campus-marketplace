"""All server-side input validation. Every function returns (clean_values, errors).

Security note (NoSQL injection): request values are only ever used after being
forced to plain strings/ints and checked against allow-lists, so a client can
never smuggle an operator like {"$ne": ""} into a query.
"""
import re

from bson import ObjectId
from bson.errors import InvalidId

from constants import ACADEMIC_YEARS, CATEGORIES, CONDITIONS, MAX_PRICE, SORT_OPTIONS

EMAIL_RE = re.compile(r"^[^@\s<>]+@[^@\s<>]+\.[^@\s<>]+$")
REG_RE = re.compile(r"^[A-Za-z0-9]{5,20}$")
PHONE_RE = re.compile(r"[6-9]\d{9}")


def to_object_id(value):
    if isinstance(value, ObjectId):
        return value
    try:
        return ObjectId(str(value))
    except (InvalidId, TypeError, ValueError):
        return None


def _text(source, key):
    value = source.get(key, "")
    return value.strip() if isinstance(value, str) else ""


def _int(text, low, high):
    if not re.fullmatch(r"\d{1,9}", text or ""):
        return None
    number = int(text)
    return number if low <= number <= high else None


def normalize_phone(raw):
    digits = re.sub(r"[\s\-()]", "", raw)
    if digits.startswith("+91"):
        digits = digits[3:]
    elif digits.startswith("91") and len(digits) == 12:
        digits = digits[2:]
    elif digits.startswith("0") and len(digits) == 11:
        digits = digits[1:]
    return digits if PHONE_RE.fullmatch(digits) else None


def _name_error(name):
    if not 2 <= len(name) <= 80 or re.search(r"[<>\d_]", name):
        return "Enter your full name (2-80 characters, no digits)."
    return None


def password_error(password):
    size = len(password.encode("utf-8"))  # bcrypt only reads the first 72 bytes
    if size < 8 or size > 72:
        return "Password must be 8-72 characters."
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        return "Password must contain at least one letter and one number."
    return None


def validate_registration(form, allowed_domains=()):
    errors, clean = {}, {}
    clean["full_name"] = _text(form, "full_name")
    if (msg := _name_error(clean["full_name"])):
        errors["full_name"] = msg

    email = _text(form, "email").lower()
    if len(email) > 254 or not EMAIL_RE.match(email):
        errors["email"] = "Enter a valid email address."
    elif allowed_domains and email.rsplit("@", 1)[1] not in allowed_domains:
        errors["email"] = "Use your university email (" + ", ".join("@" + d for d in allowed_domains) + ")."
    clean["email"] = email

    clean["registration_number"] = _text(form, "registration_number").upper()
    if not REG_RE.match(clean["registration_number"]):
        errors["registration_number"] = "Registration number must be 5-20 letters/digits."

    phone = normalize_phone(_text(form, "phone"))
    if phone is None:
        errors["phone"] = "Enter a valid 10-digit Indian mobile number."
    clean["phone"] = phone

    year = _int(_text(form, "academic_year"), min(ACADEMIC_YEARS), max(ACADEMIC_YEARS))
    if year is None:
        errors["academic_year"] = "Choose your academic year."
    clean["academic_year"] = year

    password = form.get("password", "")
    password = password if isinstance(password, str) else ""
    if (msg := password_error(password)):
        errors["password"] = msg
    elif password != form.get("confirm_password", ""):
        errors["confirm_password"] = "Passwords do not match."
    return clean, errors


def validate_profile(form):
    errors, clean = {}, {}
    clean["full_name"] = _text(form, "full_name")
    if (msg := _name_error(clean["full_name"])):
        errors["full_name"] = msg
    clean["phone"] = normalize_phone(_text(form, "phone"))
    if clean["phone"] is None:
        errors["phone"] = "Enter a valid 10-digit Indian mobile number."
    clean["academic_year"] = _int(_text(form, "academic_year"), 1, 5)
    if clean["academic_year"] is None:
        errors["academic_year"] = "Choose your academic year."
    return clean, errors


def validate_product(form):
    errors, clean = {}, {}
    clean["title"] = _text(form, "title")
    if not 3 <= len(clean["title"]) <= 100:
        errors["title"] = "Title must be 3-100 characters."
    clean["description"] = _text(form, "description")
    if not 10 <= len(clean["description"]) <= 2000:
        errors["description"] = "Description must be 10-2000 characters."
    clean["price"] = _int(_text(form, "price"), 1, MAX_PRICE)
    if clean["price"] is None:
        errors["price"] = f"Enter a whole-rupee price between 1 and {MAX_PRICE:,}."
    clean["category"] = _text(form, "category")
    if clean["category"] not in CATEGORIES:
        errors["category"] = "Choose a category from the list."
    clean["condition"] = _text(form, "condition")
    if clean["condition"] not in CONDITIONS:
        errors["condition"] = "Choose a condition from the list."
    clean["pickup_location"] = _text(form, "pickup_location")
    if len(clean["pickup_location"]) > 100:
        errors["pickup_location"] = "Pickup location must be at most 100 characters."
    return clean, errors


def validate_message(form, key="message", minimum=5):
    text = _text(form, key)
    if not minimum <= len(text) <= 500:
        return text, f"Message must be {minimum}-500 characters."
    return text, None


def validate_review(form):
    errors = {}
    rating = _int(_text(form, "rating"), 1, 5)
    if rating is None:
        errors["rating"] = "Choose a rating from 1 to 5."
    comment = _text(form, "comment")
    if len(comment) > 500:
        errors["comment"] = "Review must be at most 500 characters."
    return {"rating": rating, "comment": comment}, errors


def validate_sale(form, listed_price, allowed_buyer_ids):
    """Buyer must be someone who contacted the seller (or blank = sold outside the app)."""
    errors = {}
    buyer_raw = _text(form, "buyer_id")
    buyer_id = None
    if buyer_raw:
        if buyer_raw in allowed_buyer_ids:
            buyer_id = to_object_id(buyer_raw)
        else:
            errors["buyer_id"] = "Pick a buyer from the list."
    price_raw = _text(form, "price")
    price = listed_price if not price_raw else _int(price_raw, 1, MAX_PRICE)
    if price is None:
        errors["price"] = f"Enter a whole-rupee price between 1 and {MAX_PRICE:,}."
    return {"buyer_id": buyer_id, "price": price}, errors


def parse_filters(args):
    """Turn query-string input into a safe filter dict. Invalid values are ignored."""
    def arg(key):
        value = args.get(key, "")
        return value.strip() if isinstance(value, str) else ""

    category = arg("category")
    condition = arg("condition")
    sort = arg("sort")
    min_price = _int(arg("min_price"), 0, MAX_PRICE)
    max_price = _int(arg("max_price"), 0, MAX_PRICE)
    if min_price is not None and max_price is not None and min_price > max_price:
        min_price, max_price = max_price, min_price
    return {
        "q": arg("q")[:100],
        "category": category if category in CATEGORIES else "",
        "condition": condition if condition in CONDITIONS else "",
        "min_price": min_price,
        "max_price": max_price,
        "sort": sort if sort in SORT_OPTIONS else "newest",
        "page": _int(arg("page"), 1, 100000) or 1,
    }
