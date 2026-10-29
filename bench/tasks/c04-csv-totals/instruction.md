`totals.customer_totals(path)` reads a CSV export (`customer,amount` with a header row) and
returns a dict of customer to total amount as a string with exactly two decimals. It gives wrong totals: some sums
are off by a cent because of binary floating point, and files exported from Excel (which start with a UTF-8
byte-order mark) lose the first customer. Fix both: use exact decimal arithmetic and
read the BOM correctly. Totals are rounded half-up to 2 decimals. The tests in tests/ are incomplete; your change will also be checked by other tests. Do not change the public function names or signatures.
