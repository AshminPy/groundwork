"""Source of the 8 coding cases. `python -m bench.cases_src.build` writes tasks/, fixture/, hidden/ and oracle/."""

TEST_NOTE = ("The tests in tests/ are incomplete; your change will also be checked by other tests. "
             "Do not change the public function names or signatures.")

CASES = {}

CASES["c01-slugify-unicode"] = {
    "category": "coding",
    "instruction": f"""`textkit.slug.slugify` produces bad slugs for titles with accents and punctuation. For example
`slugify("Crème Brûlée -- Recipe!")` should return `creme-brulee-recipe`. Fix it: letters with accents become plain
ASCII letters, anything that is not a letter or digit becomes a single dash, there are no leading, trailing or
repeated dashes, and the result is lowercase. {TEST_NOTE}""",
    "fixture": {
        "textkit/__init__.py": "",
        "textkit/slug.py": '''import re


def slugify(title: str) -> str:
    """Turn a title into a URL slug."""
    s = title.lower().replace(" ", "-")
    return re.sub(r"[^a-z0-9-]", "", s)
''',
        "tests/test_slug.py": '''from textkit.slug import slugify


def test_simple():
    assert slugify("Hello World") == "hello-world"
''',
    },
    "oracle": {
        "textkit/slug.py": '''import re
import unicodedata


def slugify(title: str) -> str:
    """Turn a title into a URL slug."""
    s = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode("ascii").lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")
''',
    },
    "hidden": {
        "test_slug_hidden.py": '''from textkit.slug import slugify


def test_accents_and_punctuation():
    assert slugify("Crème Brûlée -- Recipe!") == "creme-brulee-recipe"


def test_edges_and_repeats():
    assert slugify("  --Hello,   World!!--  ") == "hello-world"


def test_digits_kept():
    assert slugify("Top 10 Tips (2026)") == "top-10-tips-2026"


def test_plain_unchanged():
    assert slugify("already-a-slug") == "already-a-slug"
''',
    },
}

CASES["c02-parse-duration"] = {
    "category": "coding",
    "instruction": f"""Implement `timeparse.parse_duration(text)` in `timeparse.py`. It takes strings such as `"1h30m"`,
`"45s"`, `"2h"`, `"1h 5m 10s"` and returns the total number of seconds as an int. Units are `h`, `m` and `s`, each
at most once, in that order, with optional spaces between parts. Anything else (an empty string, an unknown unit, a
repeated unit, units out of order, a bare number) raises `ValueError`. {TEST_NOTE}""",
    "fixture": {
        "timeparse.py": '''def parse_duration(text: str) -> int:
    """Return the number of seconds in a duration such as "1h30m"."""
    raise NotImplementedError
''',
        "tests/test_timeparse.py": '''from timeparse import parse_duration


def test_minutes():
    assert parse_duration("5m") == 300
''',
    },
    "oracle": {
        "timeparse.py": '''import re

_RX = re.compile(r"^\\s*(?:(\\d+)h)?\\s*(?:(\\d+)m)?\\s*(?:(\\d+)s)?\\s*$")


def parse_duration(text: str) -> int:
    """Return the number of seconds in a duration such as "1h30m"."""
    m = _RX.match(text or "")
    if not m or not any(m.groups()):
        raise ValueError(f"not a duration: {text!r}")
    h, mi, s = (int(g) if g else 0 for g in m.groups())
    return h * 3600 + mi * 60 + s
''',
    },
    "hidden": {
        "test_timeparse_hidden.py": '''import pytest
from timeparse import parse_duration


@pytest.mark.parametrize("text,want", [("1h30m", 5400), ("45s", 45), ("2h", 7200), ("1h 5m 10s", 3910),
                                       ("0m", 0), ("10m5s", 605)])
def test_valid(text, want):
    assert parse_duration(text) == want


@pytest.mark.parametrize("text", ["", "   ", "5", "3d", "1m1h", "1h1h", "h", "1.5h", "-2m"])
def test_invalid(text):
    with pytest.raises(ValueError):
        parse_duration(text)
''',
    },
}

CASES["c03-lru-recency"] = {
    "category": "coding",
    "instruction": f"""`lru.LRUCache` evicts the wrong entry: reading a key with `get` should make it the most recently
used, but it does not, so a key that was just read can be evicted next. Fix the cache so that both `get` (on a hit)
and `put` mark a key as most recently used, and `put` evicts the least recently used key when the cache is over
capacity. `get` on a missing key returns `None`. {TEST_NOTE}""",
    "fixture": {
        "lru.py": '''class LRUCache:
    def __init__(self, capacity: int):
        self.capacity = capacity
        self._data = {}

    def get(self, key):
        return self._data.get(key)

    def put(self, key, value):
        if key in self._data:
            del self._data[key]
        self._data[key] = value
        if len(self._data) > self.capacity:
            oldest = next(iter(self._data))
            del self._data[oldest]
''',
        "tests/test_lru.py": '''from lru import LRUCache


def test_put_get():
    c = LRUCache(2)
    c.put("a", 1)
    assert c.get("a") == 1
''',
    },
    "oracle": {
        "lru.py": '''from collections import OrderedDict


class LRUCache:
    def __init__(self, capacity: int):
        self.capacity = capacity
        self._data = OrderedDict()

    def get(self, key):
        if key not in self._data:
            return None
        self._data.move_to_end(key)
        return self._data[key]

    def put(self, key, value):
        self._data[key] = value
        self._data.move_to_end(key)
        if len(self._data) > self.capacity:
            self._data.popitem(last=False)
''',
    },
    "hidden": {
        "test_lru_hidden.py": '''from lru import LRUCache


def test_get_refreshes_recency():
    c = LRUCache(2)
    c.put("a", 1)
    c.put("b", 2)
    assert c.get("a") == 1
    c.put("c", 3)
    assert c.get("b") is None
    assert c.get("a") == 1 and c.get("c") == 3


def test_put_existing_refreshes():
    c = LRUCache(2)
    c.put("a", 1)
    c.put("b", 2)
    c.put("a", 10)
    c.put("c", 3)
    assert c.get("b") is None and c.get("a") == 10


def test_miss_does_not_insert():
    c = LRUCache(1)
    assert c.get("x") is None
    c.put("y", 1)
    assert c.get("y") == 1
''',
    },
}

CASES["c04-csv-totals"] = {
    "category": "coding",
    "instruction": f"""`totals.customer_totals(path)` reads a CSV export (`customer,amount` with a header row) and
returns a dict of customer to total amount as a string with exactly two decimals. It gives wrong totals: some sums
are off by a cent because of binary floating point, and files exported from Excel (which start with a UTF-8
byte-order mark) lose the first customer. Fix both: use exact decimal arithmetic and
read the BOM correctly. Totals are rounded half-up to 2 decimals. {TEST_NOTE}""",
    "fixture": {
        "totals.py": '''import csv


def customer_totals(path: str) -> dict:
    out = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            name = row.get("customer")
            if name is None:
                continue
            out[name] = out.get(name, 0.0) + float(row["amount"])
    return {k: f"{v:.2f}" for k, v in out.items()}
''',
        "tests/test_totals.py": '''from pathlib import Path
from totals import customer_totals


def test_basic(tmp_path=None):
    p = Path(__file__).parent / "sample.csv"
    assert customer_totals(str(p)) == {"acme": "3.00"}
''',
        "tests/sample.csv": "customer,amount\nacme,1.00\nacme,2.00\n",
    },
    "oracle": {
        "totals.py": '''import csv
from decimal import ROUND_HALF_UP, Decimal


def customer_totals(path: str) -> dict:
    out = {}
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            name = row.get("customer")
            if name is None:
                continue
            out[name] = out.get(name, Decimal("0")) + Decimal(row["amount"])
    return {k: str(v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)) for k, v in out.items()}
''',
    },
    "hidden": {
        "test_totals_hidden.py": '''from pathlib import Path
from totals import customer_totals

HERE = Path(__file__).parent


def _write(name, text, bom=False):
    p = HERE / name
    p.write_bytes((b"\\xef\\xbb\\xbf" if bom else b"") + text.encode())
    return str(p)


def test_bom_first_customer():
    p = _write("bom.csv", "customer,amount\\nzeta,1.10\\nyork,2.20\\n", bom=True)
    assert customer_totals(p) == {"zeta": "1.10", "york": "2.20"}


def test_exact_sums_and_half_up():
    rows = "".join("acme,0.10\\n" for _ in range(3)) + "beta,0.005\\nbeta,0.010\\n"
    p = _write("sums.csv", "customer,amount\\n" + rows)
    assert customer_totals(p) == {"acme": "0.30", "beta": "0.02"}


def test_many_small_amounts():
    p = _write("many.csv", "customer,amount\\n" + "c,0.01\\n" * 1000)
    assert customer_totals(p) == {"c": "10.00"}
''',
    },
}

CASES["c05-backoff-cap"] = {
    "category": "coding",
    "instruction": f"""`backoff.delays(base, cap, attempts)` should return the list of waits before each retry: retry n
(starting at 0) waits `base * 2**n` seconds, never more than `cap`. Today the first retry already waits `2 * base`,
and the cap is not applied. Fix it. `attempts` of 0 returns an empty list; a negative `base`, `cap` or `attempts`
raises `ValueError`. {TEST_NOTE}""",
    "fixture": {
        "backoff.py": '''def delays(base: float, cap: float, attempts: int) -> list:
    return [base * 2 ** (n + 1) for n in range(attempts)]
''',
        "tests/test_backoff.py": '''from backoff import delays


def test_zero():
    assert delays(1, 10, 0) == []
''',
    },
    "oracle": {
        "backoff.py": '''def delays(base: float, cap: float, attempts: int) -> list:
    if base < 0 or cap < 0 or attempts < 0:
        raise ValueError("base, cap and attempts must not be negative")
    return [min(cap, base * 2 ** n) for n in range(attempts)]
''',
    },
    "hidden": {
        "test_backoff_hidden.py": '''import pytest
from backoff import delays


def test_sequence_and_cap():
    assert delays(0.5, 3, 6) == [0.5, 1, 2, 3, 3, 3]


def test_no_cap_hit():
    assert delays(1, 100, 4) == [1, 2, 4, 8]


@pytest.mark.parametrize("args", [(-1, 5, 2), (1, -5, 2), (1, 5, -2)])
def test_negative(args):
    with pytest.raises(ValueError):
        delays(*args)
''',
    },
}

CASES["c06-semver-compare"] = {
    "category": "coding",
    "instruction": f"""Implement `semver.compare(a, b)` in `semver.py`: it returns -1, 0 or 1 as version `a` is lower
than, equal to or higher than `b`, following Semantic Versioning 2.0.0 precedence: compare MAJOR.MINOR.PATCH
numerically; a pre-release version (`1.0.0-alpha`) is lower than the release (`1.0.0`); pre-release identifiers are
compared dot by dot, numeric ones numerically and lower than alphanumeric ones, and a shorter set of identifiers is
lower when all earlier ones are equal. Build metadata (`+build.5`) is ignored. An invalid version raises
`ValueError`. {TEST_NOTE}""",
    "fixture": {
        "semver.py": '''def compare(a: str, b: str) -> int:
    raise NotImplementedError
''',
        "tests/test_semver.py": '''from semver import compare


def test_equal():
    assert compare("1.2.3", "1.2.3") == 0
''',
    },
    "oracle": {
        "semver.py": '''import re

_RX = re.compile(r"^(0|[1-9]\\d*)\\.(0|[1-9]\\d*)\\.(0|[1-9]\\d*)(?:-([0-9A-Za-z-]+(?:\\.[0-9A-Za-z-]+)*))?"
                 r"(?:\\+[0-9A-Za-z-]+(?:\\.[0-9A-Za-z-]+)*)?$")


def _parse(v):
    m = _RX.match(v or "")
    if not m:
        raise ValueError(f"invalid version {v!r}")
    pre = m.group(4)
    return tuple(int(x) for x in m.group(1, 2, 3)), (pre.split(".") if pre else None)


def _cmp_id(x, y):
    xn, yn = x.isdigit(), y.isdigit()
    if xn and yn:
        return (int(x) > int(y)) - (int(x) < int(y))
    if xn != yn:
        return -1 if xn else 1
    return (x > y) - (x < y)


def compare(a: str, b: str) -> int:
    (na, pa), (nb, pb) = _parse(a), _parse(b)
    if na != nb:
        return 1 if na > nb else -1
    if pa is None or pb is None:
        return 0 if pa is pb else (1 if pa is None else -1)
    for x, y in zip(pa, pb):
        c = _cmp_id(x, y)
        if c:
            return c
    return (len(pa) > len(pb)) - (len(pa) < len(pb))
''',
    },
    "hidden": {
        "test_semver_hidden.py": '''import pytest
from semver import compare

ORDER = ["1.0.0-alpha", "1.0.0-alpha.1", "1.0.0-alpha.beta", "1.0.0-beta", "1.0.0-beta.2", "1.0.0-beta.11",
         "1.0.0-rc.1", "1.0.0", "1.0.1", "1.1.0", "2.0.0", "10.0.0"]


def test_spec_order():
    for i, a in enumerate(ORDER):
        for j, b in enumerate(ORDER):
            assert compare(a, b) == (i > j) - (i < j), (a, b)


def test_build_ignored():
    assert compare("1.0.0+build.5", "1.0.0") == 0


@pytest.mark.parametrize("v", ["1.0", "01.0.0", "1.0.0-", "a.b.c", ""])
def test_invalid(v):
    with pytest.raises(ValueError):
        compare(v, "1.0.0")
''',
    },
}

CASES["c07-deep-merge"] = {
    "category": "coding",
    "instruction": f"""`config.merge(base, override)` should deep-merge two config dicts: nested dicts merge key by
key, any other value in `override` replaces the one in `base` (lists are replaced, not concatenated), and a value of
`None` in `override` deletes that key. Neither input may be modified. Today it only merges the top level and mutates
`base`. Fix it. {TEST_NOTE}""",
    "fixture": {
        "config.py": '''def merge(base: dict, override: dict) -> dict:
    base.update(override)
    return base
''',
        "tests/test_config.py": '''from config import merge


def test_top_level():
    assert merge({"a": 1}, {"b": 2}) == {"a": 1, "b": 2}
''',
    },
    "oracle": {
        "config.py": '''import copy


def merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in override.items():
        if v is None:
            out.pop(k, None)
        elif isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out
''',
    },
    "hidden": {
        "test_config_hidden.py": '''import copy
from config import merge


def test_nested_and_lists():
    base = {"db": {"host": "a", "pool": {"min": 1, "max": 5}}, "tags": ["x"], "keep": True}
    over = {"db": {"pool": {"max": 9}}, "tags": ["y"]}
    assert merge(base, over) == {"db": {"host": "a", "pool": {"min": 1, "max": 9}}, "tags": ["y"], "keep": True}


def test_none_deletes():
    assert merge({"a": 1, "b": {"c": 2, "d": 3}}, {"a": None, "b": {"c": None}}) == {"b": {"d": 3}}


def test_inputs_unchanged():
    base = {"a": {"b": [1]}}
    over = {"a": {"c": {"d": 1}}}
    b0, o0 = copy.deepcopy(base), copy.deepcopy(over)
    out = merge(base, over)
    out["a"]["b"].append(2)
    out["a"]["c"]["d"] = 99
    assert base == b0 and over == o0
''',
    },
}

CASES["c08-pagination-last-page"] = {
    "category": "coding",
    "instruction": f"""`pager.iter_items(fetch_page)` yields every item from a paginated API. `fetch_page(cursor)`
returns `(items, next_cursor)`, where `next_cursor` is `None` on the last page; the first call uses `cursor=None`.
Users report that the items of the last page are missing, and that an API which returns an empty page with a
non-None cursor makes it loop forever. Fix both: yield every item of every page, and stop with a `RuntimeError` if
the same cursor is returned twice. {TEST_NOTE}""",
    "fixture": {
        "pager.py": '''def iter_items(fetch_page):
    cursor = None
    while True:
        items, cursor = fetch_page(cursor)
        if cursor is None:
            break
        yield from items
''',
        "tests/test_pager.py": '''from pager import iter_items


def test_two_pages():
    pages = {None: ([1, 2], "p2"), "p2": ([3], "p3"), "p3": ([], None)}
    assert list(iter_items(lambda c: pages[c])) == [1, 2, 3]
''',
    },
    "oracle": {
        "pager.py": '''def iter_items(fetch_page):
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
''',
    },
    "hidden": {
        "test_pager_hidden.py": '''import pytest
import pager


def iter_items(fetch_page, limit=50):
    """The function under test, with a call limit so a looping implementation fails fast instead of hanging."""
    calls = {"n": 0}

    def guarded(cursor):
        calls["n"] += 1
        if calls["n"] > limit:
            raise AssertionError("fetch_page called too many times: the pager loops")
        return fetch_page(cursor)
    return pager.iter_items(guarded)


def test_last_page_kept():
    pages = {None: ([1, 2], "p2"), "p2": ([3, 4], None)}
    assert list(iter_items(lambda c: pages[c])) == [1, 2, 3, 4]


def test_single_page():
    assert list(iter_items(lambda c: (["a"], None))) == ["a"]


def test_repeated_cursor_stops():
    pages = {None: ([1], "x"), "x": ([], "x")}
    with pytest.raises(RuntimeError):
        list(iter_items(lambda c: pages[c]))


def test_cycle_stops():
    pages = {None: ([1], "a"), "a": ([2], "b"), "b": ([3], "a")}
    with pytest.raises(RuntimeError):
        list(iter_items(lambda c: pages[c]))
''',
    },
}
