`lru.LRUCache` evicts the wrong entry: reading a key with `get` should make it the most recently
used, but it does not, so a key that was just read can be evicted next. Fix the cache so that both `get` (on a hit)
and `put` mark a key as most recently used, and `put` evicts the least recently used key when the cache is over
capacity. `get` on a missing key returns `None`. The tests in tests/ are incomplete; your change will also be checked by other tests. Do not change the public function names or signatures.
