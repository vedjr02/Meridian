"""Central configuration: every filesystem path and external data location lives here.

Why one module: the non-functional requirements forbid hardcoded paths scattered across the
codebase. Anything a module needs to locate (raw data, processed outputs, the dataset source)
comes from this file, and paths can be overridden via environment variables so tests and other
machines never need code edits.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class DatasetSource:
    """Where a raw event log comes from, and how to verify it arrived intact.

    Why pin a SHA-256: the ingestion row-count test only proves parsing did not lose rows. It
    cannot detect a truncated download or an upstream file silently replaced with a different
    version. A pinned checksum guarantees every run starts from byte-identical input, which is
    what makes the pipeline's numbers reproducible for a reviewer.
    """

    name: str
    url: str
    filename: str
    sha256: str


# BPI Challenge 2017 (loan applications, Dutch financial institute), 4TU.ResearchData
# DOI 10.4121/uuid:5f3067df-f10b-45da-b98b-86ae4c7a310b, 29,658,747 bytes.
# Chosen over BPI 2012 for its larger resource population, which Module E depends on.
BPI_2017 = DatasetSource(
    name="BPI Challenge 2017",
    url=(
        "https://data.4tu.nl/file/34c3f44b-3101-4ea9-8281-e38905c68b8d/"
        "f3aec4f7-d52c-4217-82f4-57d719a8298c"
    ),
    filename="BPI Challenge 2017.xes.gz",
    sha256="183c5e5189282779c811c78c33ff936351b3dd201165d612211fc220936f8249",
)


@dataclass(frozen=True)
class Settings:
    """Resolved runtime settings.

    Why a frozen dataclass built by a function rather than module-level constants:
    `get_settings()` re-reads the environment on each call, so a test can point
    `MERIDIAN_DATA_DIR` at a temporary directory without reloading modules, and immutability
    stops one module from mutating configuration another module depends on.
    """

    data_dir: Path
    dataset: DatasetSource

    @property
    def raw_dir(self) -> Path:
        """Directory for source files exactly as downloaded, never modified in place."""
        return self.data_dir / "raw"

    @property
    def processed_dir(self) -> Path:
        """Directory for normalized and derived outputs, kept apart from raw inputs."""
        return self.data_dir / "processed"


def get_settings() -> Settings:
    """Build settings from the environment, falling back to repo-relative defaults.

    Why defaults are relative to the project root: a stranger who clones the repo must be able
    to run the pipeline with zero configuration (the README's 10-minute requirement).
    """
    data_dir = Path(os.environ.get("MERIDIAN_DATA_DIR", PROJECT_ROOT / "data"))
    return Settings(data_dir=data_dir, dataset=BPI_2017)
