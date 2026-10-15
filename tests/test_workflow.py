from db import get_db
from tests.helpers import login, make_product, make_user


def setup_trio(app):
    seller = make_user(app, "Seller One", "seller@example.com", "REG1001", "9111111111")
    buyer = make_user(app, "Buyer Two", "buyer@example.com", "REG2002", "9222222222")
    other = make_user(app, "Other Three", "other@example.com", "REG3003", "9333333333")
    return seller, buyer, other


def test_contact_requires_login_and_blocks_self(client, app):
    seller, buyer, _ = setup_trio(app)
    pid = make_product(app, seller)
    assert client.post(f"/products/{pid}/inquire", data={"message": "Hello there"}).status_code == 302
    login(client, "seller@example.com")
    assert client.post(f"/products/{pid}/inquire", data={"message": "Hello there"}).status_code == 403


def test_inquiry_flow_and_privacy(client, app):
    seller, buyer, _ = setup_trio(app)
    pid = make_product(app, seller)
    page = client.get(f"/products/{pid}").data
    assert b"9111111111" not in page and b"REG1001" not in page and b"seller@example.com" not in page
    login(client, "buyer@example.com")
    assert client.post(f"/products/{pid}/inquire", data={"message": "Is it available?"}).status_code == 302
    client.post(f"/products/{pid}/inquire", data={"message": "Again please?"})       # duplicate
    client.post(f"/products/{pid}/inquire", data={"message": "x"})                   # too short
    with app.app_context():
        assert get_db().inquiries.count_documents({}) == 1
    sent = client.get("/my/inquiries").data
    assert b"9111111111" not in sent                              # seller phone hidden until shared
    client.post("/logout")
    login(client, "seller@example.com")
    got = client.get("/my/inquiries").data
    assert b"Buyer Two" in got and b"9222222222" in got and b"buyer@example.com" in got
    assert b"REG2002" not in got                                  # registration number never shared
    with app.app_context():
        iid = get_db().inquiries.find_one()["_id"]
    client.post(f"/inquiries/{iid}/reply", data={"reply": "Yes! Library at 5pm", "share_phone": "on"})
    client.post("/logout")
    login(client, "buyer@example.com")
    sent = client.get("/my/inquiries").data
    assert b"Library at 5pm" in sent and b"9111111111" in sent    # shared only after explicit opt-in


def test_only_seller_can_reply(client, app):
    seller, buyer, other = setup_trio(app)
    pid = make_product(app, seller)
    login(client, "buyer@example.com")
    client.post(f"/products/{pid}/inquire", data={"message": "Is it available?"})
    with app.app_context():
        iid = get_db().inquiries.find_one()["_id"]
    assert client.post(f"/inquiries/{iid}/reply", data={"reply": "hijack"}).status_code == 403


def test_sale_and_review_workflow(client, app):
    seller, buyer, other = setup_trio(app)
    pid = make_product(app, seller, price=500)
    login(client, "buyer@example.com")
    client.post(f"/products/{pid}/inquire", data={"message": "Is it available?"})
    client.post("/logout")
    login(client, "seller@example.com")
    # can't name a buyer who never contacted you
    assert client.post(f"/products/{pid}/sold", data={"buyer_id": str(other)}).status_code == 400
    assert client.post(f"/products/{pid}/sold", data={"buyer_id": str(buyer), "price": "450"}).status_code == 302
    with app.app_context():
        tx = get_db().transactions.find_one({"product_id": pid})
    assert tx["buyer_id"] == buyer and tx["seller_id"] == seller and tx["price"] == 450 and tx["status"] == "COMPLETED"
    client.post("/logout")

    # seller and unrelated users cannot review
    login(client, "seller@example.com")
    assert client.post(f"/transactions/{tx['_id']}/review", data={"rating": "5"}).status_code == 403
    client.post("/logout")
    login(client, "other@example.com")
    assert client.post(f"/transactions/{tx['_id']}/review", data={"rating": "5"}).status_code == 403
    client.post("/logout")

    # the buyer can, once
    login(client, "buyer@example.com")
    assert client.post(f"/transactions/{tx['_id']}/review", data={"rating": "9"}).status_code == 302  # invalid -> flash
    with app.app_context():
        assert get_db().reviews.count_documents({}) == 0
    client.post(f"/transactions/{tx['_id']}/review", data={"rating": "4", "comment": "Great"})
    client.post(f"/transactions/{tx['_id']}/review", data={"rating": "1", "comment": "dup"})
    with app.app_context():
        assert get_db().reviews.count_documents({}) == 1
        user = get_db().users.find_one({"_id": seller})
    assert user["avg_rating"] == 4.0 and user["review_count"] == 1


def test_rating_average_is_accurate(client, app):
    seller, buyer, other = setup_trio(app)
    for who, email, rating in ((buyer, "buyer@example.com", "5"), (other, "other@example.com", "2")):
        pid = make_product(app, seller, title=f"Item {rating}")
        login(client, email)
        client.post(f"/products/{pid}/inquire", data={"message": "Interested in this"})
        client.post("/logout")
        login(client, "seller@example.com")
        client.post(f"/products/{pid}/sold", data={"buyer_id": str(who)})
        client.post("/logout")
        login(client, email)
        with app.app_context():
            tid = get_db().transactions.find_one({"product_id": pid})["_id"]
        client.post(f"/transactions/{tid}/review", data={"rating": rating})
        client.post("/logout")
    with app.app_context():
        user = get_db().users.find_one({"_id": seller})
    assert user["avg_rating"] == 3.5 and user["review_count"] == 2
    page = client.get(f"/sellers/{seller}").data
    assert b"3.5" in page and b"9111111111" not in page and b"REG1001" not in page


def test_sold_outside_app_has_no_review(client, app):
    seller, buyer, _ = setup_trio(app)
    pid = make_product(app, seller)
    login(client, "seller@example.com")
    assert client.post(f"/products/{pid}/sold", data={}).status_code == 302
    with app.app_context():
        tx = get_db().transactions.find_one({"product_id": pid})
    assert tx["buyer_id"] is None
    assert b"outside the app" in client.get("/my/sold").data


def test_cannot_contact_about_sold_item(client, app):
    seller, buyer, _ = setup_trio(app)
    pid = make_product(app, seller, status="SOLD")
    login(client, "buyer@example.com")
    client.post(f"/products/{pid}/inquire", data={"message": "Is it available?"})
    with app.app_context():
        assert get_db().inquiries.count_documents({}) == 0
