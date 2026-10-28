# DiskAlmostFull runbook

## Summary
Fires when the ledger data volume at /var/lib/ledger is above 85% used for 10m (severity page).

## Impact
At 98% usage writes stop and the service returns HTTP 507 for new entries.

## Diagnosis
Run `df -h /var/lib/ledger` and `du -sh /var/lib/ledger/segments`.

## Mitigation
Run `sudo /opt/ledger/ops/cleanup.sh`, which removes compacted segments older than 14 days.

## Escalation
If usage stays above 85% after cleanup, escalate to the storage team in #storage-oncall to grow the volume.
