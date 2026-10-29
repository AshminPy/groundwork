"""Configuration read from the environment."""
import os

# The PayAPI version this client is written against. Sent as the PayAPI-Version header.
API_VERSION = "2024-06"

BASE_URL = os.environ.get("PAYAPI_BASE_URL", "https://api.payapi.example")
TOKEN = os.environ["PAYAPI_TOKEN"]  # required, no default

DEFAULT_TIMEOUT = float(os.environ.get("PAYAPI_TIMEOUT", "7.5"))  # seconds
MAX_RETRIES = int(os.environ.get("PAYAPI_MAX_RETRIES", "3"))

# Webhook signature checks are on unless explicitly turned off.
VERIFY_SIGNATURES = os.environ.get("PAYAPI_VERIFY_SIGNATURES", "true").lower() != "false"
