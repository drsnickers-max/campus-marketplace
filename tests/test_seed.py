from db import get_db
from seed import seed
from tests.helpers import login


def test_seed_runs_and_is_repeatable(client, app):
    with app.app_context():
        seed(get_db())
        seed(get_db())                                   # idempotent
        db = get_db()
        assert db.users.count_documents({}) == 4
        assert db.products.count_documents({}) == 14
        assert db.transactions.count_documents({}) == 2 and db.reviews.count_documents({}) == 2
    assert login(client, "aarav@example.com", "Password123").status_code == 302
    assert b"Engineering Mathematics" in client.get("/").data
