from orders.processor import apply
from orders.store import Store


def test_in_order():
    s = Store()
    apply(s, {"id": "e1", "order_id": "o", "sequence": 1, "type": "created"})
    apply(s, {"id": "e2", "order_id": "o", "sequence": 2, "type": "paid", "amount": "5.00"})
    assert s.get("o")["state"] == "paid"
