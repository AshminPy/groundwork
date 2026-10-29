Finish the customer-data migration in `migrate/` (`python -m migrate INPUT OUTPUT_DIR`). INPUT is
a JSON-lines file of customer records. Version-1 records have `id`, `name`, `email`, `phone`, `signup` and
`updated_at` (an ISO timestamp). Records that already have `"schema_version": 2` are passed through unchanged, so
running the migration on its own output gives the same output. The tests in tests/ are incomplete; your change will
also be checked by other tests. Plan before you edit.

For each version-1 record, produce `{"schema_version": 2, "id", "given_name", "family_name", "email", "phone",
"signup_date", "updated_at"}`:
- **name:** trim and collapse spaces; `family_name` is the last word and `given_name` the words before it
  (`"Mary Ann  Smith"` gives `"Mary Ann"` and `"Smith"`); a single word is the `given_name`, with an empty
  `family_name`.
- **email:** trimmed and lower-cased. It is invalid unless it has exactly one `@`, a non-empty local part, and a
  domain containing a dot.
- **phone:** E.164. Keep the digits; 10 digits become `+1` and the digits; 11 digits starting with 1 become `+` and
  the digits; an input starting with `+` keeps `+` and its digits if there are 8 to 15 of them. Anything else is
  invalid.
- **signup_date:** `MM/DD/YYYY` or `YYYY-MM-DD` becomes `YYYY-MM-DD`. Anything else, or an impossible date, is
  invalid.
- A record with an invalid field goes to quarantine with the reason of the first failing check, in the order
  `invalid_email`, `invalid_phone`, `invalid_date`.
- Among valid records with the same email, keep the one with the latest `updated_at`; the others go to quarantine
  with the reason `duplicate`.
Write `OUTPUT_DIR/migrated.jsonl` (records sorted by `id`), `OUTPUT_DIR/quarantine.jsonl` (`{"id", "reason"}`,
sorted by `id`) and `OUTPUT_DIR/report.json` (`{"read", "migrated", "quarantined", "by_reason": {...}}`).
