`config.merge(base, override)` should deep-merge two config dicts: nested dicts merge key by
key, any other value in `override` replaces the one in `base` (lists are replaced, not concatenated), and a value of
`None` in `override` deletes that key. Neither input may be modified. Today it only merges the top level and mutates
`base`. Fix it. The tests in tests/ are incomplete; your change will also be checked by other tests. Do not change the public function names or signatures.
