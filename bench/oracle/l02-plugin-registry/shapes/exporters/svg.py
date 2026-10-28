from ..registry import register


@register("svg")
class SvgExporter:
    def export(self, shapes) -> str:
        parts = []
        for s in shapes:
            if s.kind == "circle":
                parts.append(f'<circle cx="{s.x}" cy="{s.y}" r="{s.size}"/>')
            else:
                parts.append(f'<rect x="{s.x}" y="{s.y}" width="{s.size}" height="{s.size}"/>')
        return "<svg>" + "".join(parts) + "</svg>"
