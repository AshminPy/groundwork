`pager.iter_items(fetch_page)` yields every item from a paginated API. `fetch_page(cursor)`
returns `(items, next_cursor)`, where `next_cursor` is `None` on the last page; the first call uses `cursor=None`.
Users report that the items of the last page are missing, and that an API which returns an empty page with a
non-None cursor makes it loop forever. Fix both: yield every item of every page, and stop with a `RuntimeError` if
the same cursor is returned twice. The tests in tests/ are incomplete; your change will also be checked by other tests. Do not change the public function names or signatures.
