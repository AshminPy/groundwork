class UploadError(Exception):
    pass


def upload_with_retries(send, max_retries: int = 3):
    """Call send() until it returns True: one attempt plus up to max_retries retries."""
    for attempt in range(max_retries):
        if send():
            return attempt + 1
    raise UploadError(f"giving up after {max_retries} attempts")
