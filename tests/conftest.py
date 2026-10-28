"""pytest: isolate telemetry for the whole suite before any test module is collected (see _isolate.py)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _isolate  # noqa: E402,F401
