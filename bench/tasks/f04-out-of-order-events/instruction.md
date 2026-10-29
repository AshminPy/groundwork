Some orders end up `paid` although they were refunded, and refund totals are sometimes counted
twice (see `logs/webhooks.log`). Find the root cause, fix it in `orders/`, and in your final answer state the root
cause in one or two sentences. Each webhook event has an `id`, an `order_id`, a per-order `sequence` (1, 2, 3, ...)
and a `type`; the provider may deliver events late, out of order, or more than once. The final state of an order must
be the one from its highest sequence seen, an event with a sequence lower than or equal to the last applied one for
that order must change nothing, and redelivering the same event must change nothing. The tests in tests/ are
incomplete; your fix will also be checked by other tests.
