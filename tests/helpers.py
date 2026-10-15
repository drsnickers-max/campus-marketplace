from services.auth import hash_password
from models import products, users

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64
PASSWORD = "Password123"


def make_user(app, name="Seller One", email="seller@example.com", reg="REG1001", phone="9876543210"):
    with app.app_context():
        return users.create_user({"full_name": name, "email": email, "registration_number": reg,
                                  "phone": phone, "academic_year": 2,
                                  "password_hash": hash_password(PASSWORD)})


def make_product(app, seller_id, title="Calculus Book", price=300, category="Books and Study Materials",
                 condition="Good", status="AVAILABLE", description="A perfectly fine item for sale."):
    with app.app_context():
        return products.create_product({"title": title, "description": description, "price": price,
                                        "category": category, "condition": condition, "images": [],
                                        "seller_id": seller_id, "status": status})


def login(client, email, password=PASSWORD):
    return client.post("/login", data={"email": email, "password": password})


def listing_form(**over):
    import io
    data = {"title": "Study Lamp", "description": "Bright LED lamp, barely used.", "price": "250",
            "category": "Hostel Essentials", "condition": "Like New", "pickup_location": "Hostel gate",
            "images": (io.BytesIO(PNG), "lamp.png")}
    data.update(over)
    return data
