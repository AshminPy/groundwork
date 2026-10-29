from uploader import upload_with_retries


def test_first_try():
    assert upload_with_retries(lambda: True) == 1
