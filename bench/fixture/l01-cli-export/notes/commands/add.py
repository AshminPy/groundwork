from datetime import datetime, timezone

from ..store import Store


def register(sub):
    p = sub.add_parser("add", help="add a note")
    p.add_argument("title")
    p.add_argument("--tag", action="append", default=[])
    p.set_defaults(func=run)


def run(args, out, err) -> int:
    n = Store(args.db).add(args.title, args.tag, datetime.now(timezone.utc).isoformat(timespec="seconds"))
    print(n.id, file=out)
    return 0
