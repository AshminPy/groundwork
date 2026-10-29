import gc
import json
import warnings
from pathlib import Path

from importer.load import import_dir, read_record

HERE = Path(__file__).parent


def test_no_unclosed_file_warning():
    p = HERE / "rec.json"
    p.write_text(json.dumps({"id": 7}))
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always", ResourceWarning)
        assert read_record(p) == {"id": 7}
        gc.collect()
    assert not [x for x in w if issubclass(x.category, ResourceWarning)]


def test_many_files():
    d = HERE / "many"
    d.mkdir(exist_ok=True)
    for i in range(300):
        (d / f"r{i:03}.json").write_text(json.dumps({"id": i}))
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always", ResourceWarning)
        out = import_dir(d)
        gc.collect()
    assert [r["id"] for r in out] == list(range(300))
    assert not [x for x in w if issubclass(x.category, ResourceWarning)]
