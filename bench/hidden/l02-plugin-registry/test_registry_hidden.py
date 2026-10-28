import csv
import io
import json

import pytest

from shapes import registry
from shapes.app import export
from shapes.model import Shape

S = [Shape("circle", 1, 2, 3), Shape("square", 4, 5, 6)]


def test_outputs_unchanged():
    assert export(S, "svg") == '<svg><circle cx="1" cy="2" r="3"/><rect x="4" y="5" width="6" height="6"/></svg>'
    assert json.loads(export(S, "json")) == [s.__dict__ for s in S]


def test_csv():
    rows = list(csv.reader(io.StringIO(export(S, "csv"))))
    assert rows == [["kind", "x", "y", "size"], ["circle", "1", "2", "3"], ["square", "4", "5", "6"]]


def test_registry_api():
    assert {"csv", "json", "svg"} <= set(registry.names())
    assert registry.names() == sorted(registry.names())
    with pytest.raises(KeyError):
        registry.get("nope")
    with pytest.raises(KeyError):
        export(S, "nope")


def test_duplicate_name():
    with pytest.raises(ValueError):
        @registry.register("svg")
        class Again:
            def export(self, shapes):
                return ""


def test_new_exporter_plugs_in():
    @registry.register("count-hidden-test")
    class Count:
        def export(self, shapes):
            return str(len(shapes))
    assert export(S, "count-hidden-test") == "2"
