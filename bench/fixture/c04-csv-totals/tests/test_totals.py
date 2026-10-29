from pathlib import Path
from totals import customer_totals


def test_basic(tmp_path=None):
    p = Path(__file__).parent / "sample.csv"
    assert customer_totals(str(p)) == {"acme": "3.00"}
