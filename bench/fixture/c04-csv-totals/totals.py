import csv


def customer_totals(path: str) -> dict:
    out = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            name = row.get("customer")
            if name is None:
                continue
            out[name] = out.get(name, 0.0) + float(row["amount"])
    return {k: f"{v:.2f}" for k, v in out.items()}
