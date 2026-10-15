import io

from bson import ObjectId

from db import get_db
from tests.helpers import PNG, listing_form, login, make_product, make_user


def test_create_listing_requires_login(client):
    assert client.get("/products/new").status_code == 302
    assert client.post("/products/new", data=listing_form()).status_code == 302


def test_create_listing_with_image(client, app):
    uid = make_user(app)
    login(client, "seller@example.com")
    res = client.post("/products/new", data=listing_form(), content_type="multipart/form-data")
    assert res.status_code == 302
    with app.app_context():
        p = get_db().products.find_one({"title": "Study Lamp"})
    assert p["seller_id"] == uid and p["status"] == "AVAILABLE" and p["price"] == 250
    assert len(p["images"]) == 1 and p["images"][0]["url"].startswith("/static/uploads/")
    assert client.get(f"/products/{p['_id']}").status_code == 200


def test_listing_validation_server_side(client, app):
    make_user(app)
    login(client, "seller@example.com")
    for bad in ({"price": "-5"}, {"price": "abc"}, {"price": "0"}, {"price": "99999999"}, {"category": "Weapons"},
                {"condition": "Haunted"}, {"title": "x"}, {"description": "short"}):
        res = client.post("/products/new", data=listing_form(**bad), content_type="multipart/form-data")
        assert res.status_code == 400, bad
    res = client.post("/products/new", data=listing_form(images=(io.BytesIO(b""), "")), content_type="multipart/form-data")
    assert res.status_code == 400                                   # no image
    with app.app_context():
        assert get_db().products.count_documents({}) == 0


def test_image_validation(client, app):
    make_user(app)
    login(client, "seller@example.com")
    cases = [(io.BytesIO(b"<?php echo 1; ?>"), "shell.php"),         # wrong extension
             (io.BytesIO(b"<?php echo 1; ?>"), "shell.png"),         # fake png (bad magic bytes)
             (io.BytesIO(PNG), "pic.gif"),                           # extension/content mismatch
             (io.BytesIO(PNG + b"0" * (5 * 1024 * 1024)), "big.png")]  # too large
    for img in cases:
        res = client.post("/products/new", data=listing_form(images=img), content_type="multipart/form-data")
        assert res.status_code == 400, img[1]


def test_only_owner_can_edit(client, app):
    owner = make_user(app)
    make_user(app, "Other", "other@example.com", "REG2002")
    pid = make_product(app, owner)
    login(client, "other@example.com")
    assert client.get(f"/products/{pid}/edit").status_code == 403
    res = client.post(f"/products/{pid}/edit", data=listing_form(title="HACKED"), content_type="multipart/form-data")
    assert res.status_code == 403
    assert client.get(f"/products/{pid}/sold").status_code == 403
    assert client.post(f"/products/{pid}/sold", data={}).status_code == 403
    with app.app_context():
        assert get_db().products.find_one({"_id": pid})["title"] == "Calculus Book"
        assert get_db().products.find_one({"_id": pid})["status"] == "AVAILABLE"


def test_owner_can_edit_and_images_kept(client, app):
    owner = make_user(app)
    login(client, "seller@example.com")
    client.post("/products/new", data=listing_form(), content_type="multipart/form-data")
    with app.app_context():
        pid = get_db().products.find_one()["_id"]
    res = client.post(f"/products/{pid}/edit", data={**listing_form(images=(io.BytesIO(b""), "")),
                                                     "title": "Better Lamp", "price": "300"},
                      content_type="multipart/form-data")
    assert res.status_code == 302
    with app.app_context():
        p = get_db().products.find_one({"_id": pid})
    assert p["title"] == "Better Lamp" and p["price"] == 300 and len(p["images"]) == 1
    # removing the only image without adding another is rejected
    res = client.post(f"/products/{pid}/edit", data={**listing_form(images=(io.BytesIO(b""), "")),
                                                     "remove_images": "0"}, content_type="multipart/form-data")
    assert res.status_code == 400


def test_mark_sold_is_atomic_and_hidden(client, app):
    owner = make_user(app)
    pid = make_product(app, owner)
    login(client, "seller@example.com")
    assert b"cannot be undone" in client.get(f"/products/{pid}/sold").data.replace(b"can't", b"cannot")  # confirmation page
    assert client.post(f"/products/{pid}/sold", data={}).status_code == 302
    client.post(f"/products/{pid}/sold", data={})                       # double click / replay
    with app.app_context():
        db = get_db()
        assert db.products.find_one({"_id": pid})["status"] == "SOLD"
        assert db.transactions.count_documents({"product_id": pid}) == 1  # only one transaction
    assert b"Calculus Book" not in client.get("/").data               # gone from public search
    detail = client.get(f"/products/{pid}")
    assert detail.status_code == 200 and b"SOLD" in detail.data        # record retained
    assert client.get(f"/products/{pid}/edit").status_code == 302      # sold = not editable
    assert b"Calculus Book" in client.get("/my/sold").data


def test_bad_ids_return_404(client, app):
    make_user(app)
    login(client, "seller@example.com")
    for url in ("/products/not-an-id", f"/products/{ObjectId()}", "/sellers/zzz", "/products/not-an-id/edit"):
        assert client.get(url).status_code == 404
