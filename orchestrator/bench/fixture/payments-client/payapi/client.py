"""HTTP client for PayAPI."""
import time
import urllib.request
import json

from . import config

RETRY_STATUSES = {429, 503}
BACKOFF_SECONDS = 0.5


class PayAPIError(Exception):
    def __init__(self, status, body):
        super().__init__(f"PayAPI returned {status}")
        self.status = status
        self.body = body


def _request(method, path, body=None, headers=None, timeout=None):
    """Send one request, retrying on RETRY_STATUSES up to config.MAX_RETRIES times."""
    url = f"{config.BASE_URL}{path}"
    hdrs = {"Authorization": f"Bearer {config.TOKEN}", "PayAPI-Version": config.API_VERSION,
            "Content-Type": "application/json", **(headers or {})}
    data = json.dumps(body).encode() if body is not None else None
    attempt = 0
    while True:
        req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout or config.DEFAULT_TIMEOUT) as resp:
                return json.loads(resp.read() or b"{}")
        except urllib.error.HTTPError as e:
            if e.code in RETRY_STATUSES and attempt < config.MAX_RETRIES:
                attempt += 1
                time.sleep(BACKOFF_SECONDS * (2 ** (attempt - 1)))
                continue
            raise PayAPIError(e.code, e.read()) from e


def fetch_invoice(invoice_id):
    """Return one invoice."""
    return _request("GET", f"/v1/invoices/{invoice_id}")


def list_invoices(offset=0, page_size=50):
    """Return one page of invoices using offset pagination."""
    return _request("GET", f"/v1/invoices?offset={offset}&limit={page_size}")


def create_refund(invoice_id, amount, currency, idempotency_key):
    """Create a refund. Retried like every other request on 429/503."""
    return _request("POST", "/v1/refunds",
                    body={"invoice": invoice_id, "amount": amount, "currency": currency},
                    headers={"Idempotency-Key": idempotency_key})
