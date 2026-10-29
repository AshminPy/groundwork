class InventoryError(Exception):
    pass


class UnknownSku(InventoryError):
    pass
