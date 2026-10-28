# Webhooks

PayAPI signs every webhook with HMAC-SHA256. `payapi.webhooks.verify_signature` checks the signature.

Signatures older than 5 minutes are rejected, which protects against replayed webhooks.
