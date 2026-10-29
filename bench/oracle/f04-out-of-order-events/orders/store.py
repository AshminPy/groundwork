class Store:
    def __init__(self):
        self.orders = {}
        self.seen_events = set()

    def get(self, order_id):
        return self.orders.setdefault(order_id, {"state": None, "refunded_total": 0.0, "last_sequence": 0})
