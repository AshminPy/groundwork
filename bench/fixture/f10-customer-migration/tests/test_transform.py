from migrate.transform import transform


def test_basic():
    r = transform({"id": 1, "name": "Ada Lovelace", "email": "ada@example.com", "phone": "+447700900123",
                   "signup": "2026-01-02", "updated_at": "2026-01-02T00:00:00Z"})
    assert r["given_name"] == "Ada" and r["family_name"] == "Lovelace"
