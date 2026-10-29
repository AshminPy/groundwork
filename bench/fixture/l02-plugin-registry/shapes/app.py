import json

from .model import Shape


def _svg(shapes):
    parts = []
    for s in shapes:
        if s.kind == "circle":
            parts.append(f'<circle cx="{s.x}" cy="{s.y}" r="{s.size}"/>')
        else:
            parts.append(f'<rect x="{s.x}" y="{s.y}" width="{s.size}" height="{s.size}"/>')
    return "<svg>" + "".join(parts) + "</svg>"


def _json(shapes):
    return json.dumps([s.__dict__ for s in shapes])


def export(shapes: list, fmt: str) -> str:
    if fmt == "svg":
        return _svg(shapes)
    if fmt == "json":
        return _json(shapes)
    raise KeyError(fmt)
