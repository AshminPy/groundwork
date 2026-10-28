import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class Note:
    id: int
    title: str
    tags: list = field(default_factory=list)
    created: str = ""


class Store:
    def __init__(self, path: str):
        self.path = Path(path)

    def all(self) -> list:
        if not self.path.exists():
            return []
        return [Note(**d) for d in json.loads(self.path.read_text())]

    def add(self, title: str, tags: list, created: str) -> Note:
        notes = self.all()
        n = Note(id=max((x.id for x in notes), default=0) + 1, title=title, tags=tags, created=created)
        self.path.write_text(json.dumps([asdict(x) for x in notes + [n]]))
        return n
