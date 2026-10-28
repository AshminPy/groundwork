The `shapes` app hard-codes its exporters in `shapes/app.py`. Replace that with a registry:
- `shapes/registry.py` with a decorator `register(name)` that registers an exporter class under a name, `get(name)`
  that returns an instance (raising `KeyError` with a clear message for an unknown name), and `names()` that returns
  the registered names sorted;
- registering the same name twice raises `ValueError`;
- move the existing exporters (`svg`, `json`) into `shapes/exporters/` modules that register themselves, and add a
  `csv` exporter that writes `kind,x,y,size` rows with a header;
- `shapes.app.export(shapes, fmt)` keeps its signature and output for `svg` and `json`, and now supports `csv`.
The tests in tests/ are incomplete; your change will also be checked by other tests. Plan the change before you edit, and keep the existing public API working.
