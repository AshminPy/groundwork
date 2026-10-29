import csv
import io

from ..registry import register


@register("csv")
class CsvExporter:
    def export(self, shapes) -> str:
        buf = io.StringIO()
        w = csv.writer(buf, lineterminator="\n")
        w.writerow(["kind", "x", "y", "size"])
        for s in shapes:
            w.writerow([s.kind, s.x, s.y, s.size])
        return buf.getvalue()
