import mongomock

from app import create_app
from tests.helpers import PASSWORD, login, make_user


def build(**cfg):
    base = {"TESTING": True, "MONGO_DB_NAME": "sec", "BCRYPT_ROUNDS": 4, "SECRET_KEY": "s"}
    base.update(cfg)
    return create_app(test_config=base, mongo_client=mongomock.MongoClient())


def test_csrf_enforced_when_enabled():
    app = build(WTF_CSRF_ENABLED=True, RATELIMIT_ENABLED=False)
    make_user(app)
    client = app.test_client()
    assert client.post("/login", data={"email": "seller@example.com", "password": PASSWORD}).status_code == 400
    page = client.get("/login").data.decode()
    token = page.split('name="csrf_token" value="')[1].split('"')[0]
    res = client.post("/login", data={"email": "seller@example.com", "password": PASSWORD, "csrf_token": token})
    assert res.status_code == 302


def test_logout_requires_post(client):
    assert client.get("/logout").status_code == 405


def test_rate_limit_on_login():
    app = build(WTF_CSRF_ENABLED=False, RATELIMIT_ENABLED=True)
    client = app.test_client()
    codes = [client.post("/login", data={"email": "a@b.co", "password": "x"}).status_code for _ in range(12)]
    assert 429 in codes


def test_nosql_injection_attempts_are_harmless(client, app):
    make_user(app)
    # operator-style keys in forms/queries are just ignored strings
    res = client.post("/login", data={"email[$ne]": "x", "password[$ne]": "x"})
    assert res.status_code == 401
    res = client.post("/login", data={"email": '{"$ne": ""}', "password": "{'$ne': ''}"})
    assert res.status_code == 401
    assert client.get("/?q[$ne]=x&category[$ne]=x&min_price[$gt]=0").status_code == 200
    assert client.get('/?category={"$ne":""}').status_code == 200


def test_xss_is_escaped(client, app):
    from tests.helpers import make_product
    s = make_user(app)
    make_product(app, s, title="<script>alert(1)</script>", description="<img src=x onerror=alert(1)> nice item")
    html = client.get("/").data
    assert b"<script>alert(1)</script>" not in html and b"&lt;script&gt;" in html


def test_security_headers_and_no_hash_leak(client, app):
    res = client.get("/")
    assert res.headers["X-Frame-Options"] == "DENY" and "default-src 'self'" in res.headers["Content-Security-Policy"]
    uid = make_user(app)
    login(client, "seller@example.com")
    body = client.get("/profile").data + client.get(f"/sellers/{uid}").data
    assert b"$2b$" not in body and b"password_hash" not in body


def test_session_cookie_flags(client, app):
    make_user(app)
    res = login(client, "seller@example.com")
    cookie = res.headers.get("Set-Cookie", "")
    assert "HttpOnly" in cookie and "SameSite=Lax" in cookie


def test_require_login_to_browse_option():
    app = build(WTF_CSRF_ENABLED=False, RATELIMIT_ENABLED=False, REQUIRE_LOGIN_TO_BROWSE=True)
    client = app.test_client()
    assert client.get("/").status_code == 302
    assert client.get("/login").status_code == 200


def test_error_pages(client):
    res = client.get("/does-not-exist")
    assert res.status_code == 404 and b"Not found" in res.data
