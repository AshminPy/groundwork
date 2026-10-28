from pathlib import Path
from totals import customer_totals

HERE = Path(__file__).parent


def _write(name, text, bom=False):
    p = HERE / name
    p.write_bytes((b"\xef\xbb\xbf" if bom else b"") + text.encode())
    return str(p)


def test_bom_first_customer():
    p = _write("bom.csv", "customer,amount\nzeta,1.10\nyork,2.20\n", bom=True)
    assert customer_totals(p) == {"zeta": "1.10", "york": "2.20"}


def test_exact_sums_and_half_up():
    rows = "".join("acme,0.10\n" for _ in range(3)) + "beta,0.005\nbeta,0.010\n"
    p = _write("sums.csv", "customer,amount\n" + rows)
    assert customer_totals(p) == {"acme": "0.30", "beta": "0.02"}


def test_many_small_amounts():
    p = _write("many.csv", "customer,amount\n" + "c,0.01\n" * 1000)
    assert customer_totals(p) == {"c": "10.00"}
