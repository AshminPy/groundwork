import argparse
import sys

from .commands import add, export, list_cmd


def main(argv=None, out=None, err=None) -> int:
    out, err = out or sys.stdout, err or sys.stderr
    ap = argparse.ArgumentParser(prog="notes")
    ap.add_argument("--db", default="notes.json")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for mod in (add, list_cmd, export):
        mod.register(sub)
    args = ap.parse_args(argv)
    return args.func(args, out, err)
