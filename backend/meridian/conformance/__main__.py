"""Allow `python -m meridian.conformance` to run token-replay conformance."""

import sys

from meridian.conformance.pipeline import main

if __name__ == "__main__":
    sys.exit(main())
