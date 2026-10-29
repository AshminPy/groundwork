Add an `export` subcommand to the `notes` CLI (`notes/cli.py`, `notes/store.py`,
`notes/commands/`). `python -m notes export --format csv --out FILE` writes every note to FILE as CSV with the header
`id,title,tags,created` (tags joined with `;`, notes ordered by id); `--format json` writes a JSON list of objects
with the same four keys (tags as a list). Without `--out` it prints to stdout. `--tag TAG` exports only notes that
have that tag. An unknown format exits with status 2 and an error on stderr. The store path comes from `--db` as for
the other subcommands. The tests in tests/ are incomplete; your change will also be checked by other tests. Plan the change before you edit, and keep the existing public API working.
