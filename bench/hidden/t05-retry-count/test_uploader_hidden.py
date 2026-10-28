import pytest
from uploader import UploadError, upload_with_retries


def _sender(succeed_on):
    calls = {"n": 0}

    def send():
        calls["n"] += 1
        return calls["n"] == succeed_on
    return send, calls


def test_succeeds_on_last_retry():
    send, calls = _sender(4)
    assert upload_with_retries(send, max_retries=3) == 4


def test_gives_up_after_all_retries():
    send, calls = _sender(99)
    with pytest.raises(UploadError):
        upload_with_retries(send, max_retries=3)
    assert calls["n"] == 4


def test_zero_retries():
    send, calls = _sender(99)
    with pytest.raises(UploadError):
        upload_with_retries(send, max_retries=0)
    assert calls["n"] == 1
