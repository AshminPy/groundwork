from ..store import Store


def register(sub):
    p = sub.add_parser("list", help="list notes")
    p.set_defaults(func=run)


def run(args, out, err) -> int:
    for n in Store(args.db).all():
        print(f"{n.id}\t{n.title}", file=out)
    return 0
