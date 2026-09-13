"""Allow `python -m meridian.ingestion` to run the ingestion pipeline."""

import sys

from meridian.ingestion.pipeline import main

if __name__ == "__main__":
    sys.exit(main())
