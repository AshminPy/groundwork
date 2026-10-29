import csv
import json
import sys

from ..store import Store

FORMATS = ("csv", "json")


def register(sub):
    p = sub.add_parser("export", help="export notes")
    p.add_argument("--format", default="csv")
    p.add_argument("--out")
    p.add_argument("--tag")
    p.set_defaults(func=run)


def run(args, out, err) -> int:
    if args.format not in FORMATS:
        print(f"unknown format {args.format!r}; use one of {', '.join(FORMATS)}", file=err)
        return 2
    notes = sorted(Store(args.db).all(), key=lambda n: n.id)
    if args.tag:
        notes = [n for n in notes if args.tag in n.tags]
    f = open(args.out, "w", newline="", encoding="utf-8") if args.out else out
    try:
        if args.format == "csv":
            w = csv.writer(f, lineterminator="\n")
            w.writerow(["id", "title", "tags", "created"])
            for n in notes:
                w.writerow([n.id, n.title, ";".join(n.tags), n.created])
        else:
            json.dump([{"id": n.id, "title": n.title, "tags": n.tags, "created": n.created} for n in notes], f)
    finally:
        if args.out:
            f.close()
    return 0
