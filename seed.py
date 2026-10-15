"""Load sample data:  python seed.py        (adds data)
                     python seed.py --reset (wipes the database first)
All sample accounts use the password  Password123
"""
import sys
from datetime import datetime, timedelta, timezone

from app import create_app
from db import get_db
from models import inquiries, products, reviews, transactions, users
from services.auth import hash_password

PASSWORD = "Password123"
USERS = [
    ("Aarav Sharma", "aarav@example.com", "MUJ2301", "9876500001", 2),
    ("Diya Patel", "diya@example.com", "MUJ2302", "9876500002", 3),
    ("Kabir Singh", "kabir@example.com", "MUJ2303", "9876500003", 1),
    ("Meera Nair", "meera@example.com", "MUJ2304", "9876500004", 4),
]
ITEMS = [  # (seller idx, title, description, price, category, condition)
    (0, "Engineering Mathematics Textbook", "B.S. Grewal, lightly highlighted. Great for 1st year.", 350, "Books and Study Materials", "Good"),
    (0, "Scientific Calculator Casio fx-991", "Works perfectly. Includes cover.", 700, "Electronics", "Like New"),
    (1, "Study Table with Drawer", "Sturdy wooden table, hostel-friendly size.", 1800, "Furniture", "Good"),
    (1, "Badminton Racket Set", "Two Yonex rackets and 3 shuttlecocks.", 900, "Sports Equipment", "Good"),
    (1, "Bedside Lamp", "LED lamp with adjustable brightness.", 250, "Hostel Essentials", "Like New"),
    (2, "Bluetooth Headphones", "Battery lasts ~20 hours. Slight scratch on left cup.", 1200, "Electronics", "Fair"),
    (2, "Denim Jacket (M)", "Worn twice. Too small for me.", 600, "Clothing and Shoes", "Like New"),
    (3, "Data Structures Notes Bundle", "Handwritten notes, whole semester, neatly organised.", 150, "Books and Study Materials", "Good"),
    (3, "Backpack 30L", "Waterproof, many pockets.", 500, "Accessories", "Good"),
    (3, "Electric Kettle 1.5L", "Perfect for hostel rooms.", 400, "Hostel Essentials", "Fair"),
    (0, "Arduino Starter Kit", "Complete kit with sensors and jumper wires.", 1100, "Electronics", "New"),
    (1, "Mini Fridge", "Works great, 45L. Pickup from hostel block C.", 4500, "Hostel Essentials", "Good"),
    (2, "Chess Set (Wooden)", "Tournament size board with weighted pieces.", 800, "Sports Equipment", "Like New"),
    (3, "Drafter and Geometry Box", "Used for one semester.", 200, "Accessories", "Good"),
]


def seed(db, reset=False):
    if reset:
        for name in ("users", "products", "transactions", "reviews", "inquiries"):
            db[name].delete_many({})
    ids = []
    for name, email, reg, phone, year in USERS:
        existing = users.get_by_email(email)
        if existing:
            ids.append(existing["_id"])
            continue
        ids.append(users.create_user({"full_name": name, "email": email, "registration_number": reg,
                                      "phone": phone, "academic_year": year,
                                      "password_hash": hash_password(PASSWORD)}))
    if db.products.count_documents({"seller_id": {"$in": ids}}) == 0:
        created = []
        for n, (s, title, desc, price, cat, cond) in enumerate(ITEMS):
            pid = products.create_product({"title": title, "description": desc, "price": price,
                                           "category": cat, "condition": cond, "images": [],
                                           "pickup_location": "Library main gate" if n % 3 == 0 else "",
                                           "seller_id": ids[s], "status": "AVAILABLE"})
            db.products.update_one({"_id": pid}, {"$set": {"created_at": datetime.now(timezone.utc) - timedelta(hours=n)}})
            created.append(pid)
        # two completed sales with reviews so ratings show up
        for pid, buyer in ((created[4], ids[0]), (created[6], ids[3])):
            product = products.get_product(pid)
            inquiries.create(product, buyer, "Is this still available?")
            sold = products.mark_sold(pid, product["seller_id"])
            tx = transactions.get(transactions.create(sold, buyer, sold["price"]))
            reviews.create(tx, 5 if pid == created[4] else 4, "Smooth, friendly meetup.")
            reviews.recalculate_seller_rating(product["seller_id"])
    return ids


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        seed(get_db(), reset="--reset" in sys.argv)
    print("Seeded. Log in with e.g. aarav@example.com / Password123")
