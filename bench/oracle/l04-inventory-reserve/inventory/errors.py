class InventoryError(Exception):
    pass


class UnknownSku(InventoryError):
    pass


class UnknownOrder(InventoryError):
    pass


class InvalidQuantity(InventoryError):
    pass


class InsufficientStock(InventoryError):
    def __init__(self, sku: str, requested: int, available: int):
        super().__init__(f"{sku}: requested {requested}, available {available}")
        self.sku, self.requested, self.available = sku, requested, available
