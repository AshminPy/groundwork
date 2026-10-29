import copy
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
