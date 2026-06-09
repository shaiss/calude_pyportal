import os
import sys

# Device modules live in flash/ and are import-pure (json/struct only), so they
# import cleanly under host CPython for unit testing.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "flash"))
