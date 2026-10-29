from orders.processor import apply
from orders.store import Store


def ev(i, order, seq, typ, amount=None):
    e = {"id": i, "order_id": order, "sequence": seq, "type": typ}
    if amount is not None:
        e["amount"] = amount
    return e


def test_late_paid_does_not_override_refund():
    s = Store()
    for e in [ev("late-1", "o9", 1, "created"), ev("late-3", "o9", 3, "refunded", "40.00"), ev("late-2", "o9", 2, "paid", "40.00")]:
        apply(s, e)
    assert s.get("o9")["state"] == "refunded" and s.get("o9")["refunded_total"] == 40.0


def test_redelivery_is_idempotent():
    s = Store()
    for e in [ev("redeliver-1", "o1", 1, "created"), ev("redeliver-2", "o1", 2, "refunded", "10.00"), ev("redeliver-2", "o1", 2, "refunded", "10.00")]:
        apply(s, e)
    assert s.get("o1")["refunded_total"] == 10.0


def test_equal_sequence_other_event_ignored():
    s = Store()
    apply(s, ev("eq-a", "o2", 1, "created"))
    apply(s, ev("eq-b", "o2", 2, "paid", "1.00"))
    apply(s, ev("eq-c", "o2", 2, "cancelled"))
    assert s.get("o2")["state"] == "paid"


def test_sequences_are_per_order():
    s = Store()
    apply(s, ev("per-x1", "A", 5, "paid", "1.00"))
    apply(s, ev("per-y1", "B", 1, "created"))
    assert s.get("B")["state"] == "created" and s.get("A")["state"] == "paid"


def test_all_permutations_same_final_state():
    import itertools
    for n, order in enumerate(itertools.permutations(range(3))):
        oid = f"perm{n}"
        events = [ev(f"{oid}-1", oid, 1, "created"), ev(f"{oid}-2", oid, 2, "paid", "9.00"),
                  ev(f"{oid}-3", oid, 3, "refunded", "9.00")]
        s = Store()
        for i in order:
            apply(s, events[i])
        apply(s, events[2])
        assert s.get(oid)["state"] == "refunded"
        assert s.get(oid)["refunded_total"] == 9.0
