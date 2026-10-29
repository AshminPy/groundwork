from email.utils import parsedate_to_datetime

RETRY_STATUSES = {429, 502, 503, 504}
SAFE_METHODS = {"GET", "PUT", "DELETE"}


def retryable_request(method: str, headers: dict) -> bool:
    return method.upper() in SAFE_METHODS or (method.upper() == "POST" and bool(headers.get("Idempotency-Key")))


def wait_seconds(n: int, response_headers: dict | None, now: float, max_backoff: float) -> float:
    ra = (response_headers or {}).get("Retry-After")
    wait = None
    if ra is not None:
        ra = str(ra).strip()
        if ra.isdigit():
            wait = float(ra)
        else:
            try:
                wait = parsedate_to_datetime(ra).timestamp() - now
            except (TypeError, ValueError):
                wait = None
    if wait is None:
        wait = 0.5 * 2 ** (n - 1)
    return max(0.0, min(max_backoff, wait))
