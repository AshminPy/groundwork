from . import exporters  # noqa: F401  (registers the built-in exporters)
from . import registry


def export(shapes: list, fmt: str) -> str:
    return registry.get(fmt).export(shapes)
