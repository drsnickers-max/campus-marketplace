from db import get_db
from tests.helpers import PASSWORD, login, make_user


def reg(**over):
    data = {"full_name": "Test Student", "email": "test@example.com", "registration_number": "RG1001",
            "phone": "98765 43210", "academic_year": "2", "password": PASSWORD, "confirm_password": PASSWORD}
    data.update(over)
    return data


def test_register_success_hashes_password(client, app):
    res = client.post("/register", data=reg())
    assert res.status_code == 302
    with app.app_context():
        user = get_db().users.find_one({"email": "test@example.com"})
    assert user["password_hash"] != PASSWORD.encode()
    assert user["password_hash"].startswith(b"$2")           # bcrypt
    assert user["phone"] == "9876543210"                       # normalised
    assert user["avg_rating"] == 0 and user["review_count"] == 0


def test_duplicate_email_and_registration_rejected(client):
    assert client.post("/register", data=reg()).status_code == 302
    assert client.post("/register", data=reg(registration_number="OTHER99")).status_code == 400
    assert client.post("/register", data=reg(email="new@example.com")).status_code == 400


def test_registration_validation(client):
    for bad in (reg(email="nope"), reg(phone="123"), reg(password="short1", confirm_password="short1"),
                reg(password="onlyletters", confirm_password="onlyletters"),
                reg(confirm_password="Different123"), reg(academic_year="9"),
                reg(registration_number="a b"), reg(full_name="<b>x</b>")):
        assert client.post("/register", data=bad).status_code == 400


def test_login_logout_flow(client, app):
    make_user(app)
    assert login(client, "seller@example.com").status_code == 302
    assert client.get("/profile").status_code == 200
    assert client.post("/logout").status_code == 302
    assert client.get("/profile").status_code == 302          # redirected to login


def test_login_failure_is_generic(client, app):
    make_user(app)
    wrong_pw = login(client, "seller@example.com", "WrongPass1")
    unknown = login(client, "ghost@example.com")
    assert wrong_pw.status_code == unknown.status_code == 401
    assert b"Invalid email or password" in wrong_pw.data
    assert b"Invalid email or password" in unknown.data


def test_open_redirect_blocked(client, app):
    make_user(app)
    res = client.post("/login?next=https://evil.com", data={"email": "seller@example.com", "password": PASSWORD})
    assert res.headers["Location"] == "/"
    res = client.post("/login?next=//evil.com", data={"email": "seller@example.com", "password": PASSWORD})
    assert res.headers["Location"] == "/"


def test_profile_update_only_permitted_fields(client, app):
    uid = make_user(app)
    login(client, "seller@example.com")
    res = client.post("/profile/edit", data={"full_name": "New Name", "phone": "9123456789", "academic_year": "3",
                                             "email": "hacker@example.com", "registration_number": "HACK1",
                                             "avg_rating": "5"})
    assert res.status_code == 302
    with app.app_context():
        user = get_db().users.find_one({"_id": uid})
    assert user["full_name"] == "New Name" and user["academic_year"] == 3
    assert user["email"] == "seller@example.com" and user["registration_number"] == "REG1001"
    assert user["avg_rating"] == 0


def test_profile_edit_validation(client, app):
    make_user(app)
    login(client, "seller@example.com")
    assert client.post("/profile/edit", data={"full_name": "A", "phone": "1", "academic_year": "x"}).status_code == 400
