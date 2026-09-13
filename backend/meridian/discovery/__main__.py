"""Allow `python -m meridian.discovery` to run Module A end to end."""

import sys

from meridian.discovery.pipeline import main

if __name__ == "__main__":
    sys.exit(main())
