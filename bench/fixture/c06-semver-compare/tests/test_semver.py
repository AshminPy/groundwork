from semver import compare


def test_equal():
    assert compare("1.2.3", "1.2.3") == 0
