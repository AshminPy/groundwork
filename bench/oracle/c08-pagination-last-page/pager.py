def iter_items(fetch_page):
    cursor, seen = None, set()
    while True:
        items, nxt = fetch_page(cursor)
        yield from items
        if nxt is None:
            return
        if nxt in seen or nxt == cursor:
            raise RuntimeError(f"cursor {nxt!r} returned twice")
        seen.add(nxt)
        cursor = nxt
