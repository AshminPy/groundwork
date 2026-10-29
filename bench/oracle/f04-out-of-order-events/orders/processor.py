STATES = {"created": "created", "paid": "paid", "refunded": "refunded", "cancelled": "cancelled"}


def apply(store, event: dict) -> None:
    if event["id"] in store.seen_events:
        return
    store.seen_events.add(event["id"])
    order = store.get(event["order_id"])
    if event["sequence"] <= order["last_sequence"]:
        return
    order["last_sequence"] = event["sequence"]
    order["state"] = STATES[event["type"]]
    if event["type"] == "refunded":
        order["refunded_total"] += float(event.get("amount", 0))
