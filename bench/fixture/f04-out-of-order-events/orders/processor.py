STATES = {"created": "created", "paid": "paid", "refunded": "refunded", "cancelled": "cancelled"}


def apply(store, event: dict) -> None:
    order = store.get(event["order_id"])
    order["state"] = STATES[event["type"]]
    if event["type"] == "refunded":
        order["refunded_total"] += float(event.get("amount", 0))
