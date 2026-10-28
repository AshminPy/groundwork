from shapes.app import export
from shapes.model import Shape


def test_svg():
    assert export([Shape("circle", 1, 2, 3)], "svg") == '<svg><circle cx="1" cy="2" r="3"/></svg>'
