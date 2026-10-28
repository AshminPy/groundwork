#!/bin/sh
# Deletes compacted ledger segments older than 14 days. Safe while the service runs.
set -eu
find /var/lib/ledger/segments -name '*.compacted' -mtime +14 -delete
