Add stock reservations to the inventory service (`inventory/models.py`, `inventory/service.py`,
`inventory/errors.py`):
- `Inventory.reserve(sku, qty, order_id) -> Reservation`: holds `qty` units for an order. Available stock is
  on-hand minus all active reservations. Raise `UnknownSku` for an unknown sku, `InvalidQuantity` for qty < 1, and
  `InsufficientStock` (with `.available` set to the available amount) when there is not enough. Reserving again for
  the same order and sku replaces that order's previous reservation for the sku (it does not add to it).
- `Inventory.release(order_id)`: drops every reservation of that order; unknown orders are a no-op.
- `Inventory.commit(order_id)`: turns the order's reservations into shipped stock (on-hand goes down) and removes
  them; committing an unknown order raises `UnknownOrder`.
- `Inventory.available(sku)` returns the available amount.
All four errors subclass the existing `InventoryError`. The tests in tests/ are incomplete; your change will also be checked by other tests. Plan the change before you edit, and keep the existing public API working.
