class Store:
    def __init__(self):
        self.orders = {}

    def get(self, order_id):
        return self.orders.setdefault(order_id, {"state": None, "refunded_total": 0.0})
