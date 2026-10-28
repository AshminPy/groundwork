import io
from notes.cli import main


def test_add_and_list(tmp_path=None):
    import tempfile, os
    d = tempfile.mkdtemp(dir=".")
    db = os.path.join(d, "n.json")
    assert main(["--db", db, "add", "hello"], io.StringIO()) == 0
    out = io.StringIO()
    main(["--db", db, "list"], out)
    assert "hello" in out.getvalue()
