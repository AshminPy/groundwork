import csv
from decimal import ROUND_HALF_UP, Decimal


def customer_totals(path: str) -> dict:
    out = {}
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            name = row.get("customer")
            if name is None:
                continue
            out[name] = out.get(name, Decimal("0")) + Decimal(row["amount"])
    return {k: str(v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)) for k, v in out.items()}
