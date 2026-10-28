def iter_items(fetch_page):
    cursor = None
    while True:
        items, cursor = fetch_page(cursor)
        if cursor is None:
            break
        yield from items
