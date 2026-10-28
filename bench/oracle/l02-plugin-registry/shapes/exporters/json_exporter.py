import json

from ..registry import register


@register("json")
class JsonExporter:
    def export(self, shapes) -> str:
        return json.dumps([s.__dict__ for s in shapes])
