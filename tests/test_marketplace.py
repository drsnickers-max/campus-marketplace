from tests.helpers import make_product, make_user


def seed_items(app, per_page=10):
    app.config["PER_PAGE"] = per_page
    s = make_user(app)
    make_product(app, s, "Calculus Book", 300, "Books and Study Materials", "Good", description="Maths textbook")
    make_product(app, s, "Gaming Laptop", 40000, "Electronics", "Like New", description="Fast machine for study")
    make_product(app, s, "Study Table", 1500, "Furniture", "Fair", description="Wooden desk")
    make_product(app, s, "Old Lamp", 100, "Hostel Essentials", "Fair", status="SOLD")
    make_product(app, s, "Physics Book", 250, "Books and Study Materials", "New", description="Optics and waves")


def test_only_available_shown(client, app):
    seed_items(app)
    html = client.get("/").data
    assert b"Calculus Book" in html and b"Old Lamp" not in html


def test_search_title_and_description(client, app):
    seed_items(app)
    assert b"Calculus Book" in client.get("/?q=calculus").data
    html = client.get("/?q=maths").data                    # matches description only
    assert b"Calculus Book" in html and b"Gaming Laptop" not in html
    assert b"No items match" in client.get("/?q=zzzzzz").data
    assert client.get("/?q=(.*)[").status_code == 200       # regex characters are treated literally


def test_filters(client, app):
    seed_items(app)
    html = client.get("/?category=Electronics").data
    assert b"Gaming Laptop" in html and b"Calculus Book" not in html
    html = client.get("/?condition=Fair").data
    assert b"Study Table" in html and b"Calculus Book" not in html
    html = client.get("/?min_price=200&max_price=1000").data
    assert b"Calculus Book" in html and b"Physics Book" in html and b"Gaming Laptop" not in html
    assert b"Calculus Book" in client.get("/?min_price=1000&max_price=200").data  # swapped min/max


def test_sorting(client, app):
    seed_items(app)
    low = client.get("/?sort=price_asc").data
    assert low.index(b"Physics Book") < low.index(b"Calculus Book") < low.index(b"Study Table")
    high = client.get("/?sort=price_desc").data
    assert high.index(b"Gaming Laptop") < high.index(b"Study Table")
    new = client.get("/").data                                # newest first = last created first
    assert new.index(b"Physics Book") < new.index(b"Calculus Book")


def test_pagination(client, app):
    seed_items(app, per_page=3)                               # 4 available, 3 per page
    p1, p2 = client.get("/").data, client.get("/?page=2").data
    assert b"Page 1 of 2" in p1 and b"Page 2 of 2" in p2
    assert b"Next" in p1 and b"Previous" in p2
    assert b"Calculus Book" in p2 and b"Calculus Book" not in p1   # oldest item is on page 2
    assert client.get("/?page=999").status_code == 200       # clamps to last page
    assert client.get("/?page=abc").status_code == 200


def test_invalid_filters_ignored_not_errors(client, app):
    seed_items(app)
    html = client.get("/?category=Nope&condition=Nope&sort=evil&min_price=abc").data
    assert b"Calculus Book" in html


def test_empty_state(client):
    assert b"No items listed yet" in client.get("/").data
    assert client.get("/health").get_json() == {"status": "ok"}
