# ledger ops

- Data lives on its own volume, mounted at /var/lib/ledger.
- Disk usage: `df -h /var/lib/ledger` and `du -sh /var/lib/ledger/segments`.
- Cleanup: `sudo /opt/ledger/ops/cleanup.sh` (removes compacted segments older than 14 days).
- If usage stays above 85% after cleanup, the volume must be grown: escalate to the storage team (#storage-oncall).
- Writes stop at 98% usage; the service then returns HTTP 507 for new entries.
