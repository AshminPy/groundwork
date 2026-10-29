Implement `semver.compare(a, b)` in `semver.py`: it returns -1, 0 or 1 as version `a` is lower
than, equal to or higher than `b`, following Semantic Versioning 2.0.0 precedence: compare MAJOR.MINOR.PATCH
numerically; a pre-release version (`1.0.0-alpha`) is lower than the release (`1.0.0`); pre-release identifiers are
compared dot by dot, numeric ones numerically and lower than alphanumeric ones, and a shorter set of identifiers is
lower when all earlier ones are equal. Build metadata (`+build.5`) is ignored. An invalid version raises
`ValueError`. The tests in tests/ are incomplete; your change will also be checked by other tests. Do not change the public function names or signatures.
