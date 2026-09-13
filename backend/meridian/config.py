"""Central configuration: every filesystem path and external data location lives here.

Why one module: the non-functional requirements forbid hardcoded paths scattered across the
codebase. Anything a module needs to locate (raw data, processed outputs, the dataset source,
the database) comes from this file, and values can be overridden via environment variables so
tests and other machines never need code edits.
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

    Why `outcome_activities` lives here: which activities mark a case's outcome is knowledge
    about this specific dataset, not about ingestion logic, so it belongs with the dataset.
    """

    name: str
    url: str
    filename: str
    sha256: str
    outcome_activities: tuple[tuple[str, str], ...] = ()


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
    # Applications end in one of these states. Measured on the raw log: 17,228 A_Pending,
    # 10,431 A_Cancelled, 3,752 A_Denied, and 98 cases with none (still open when the log was
    # extracted; their outcome stays NULL). O_Accepted also occurs exactly 17,228 times, which is
    # consistent with A_Pending being the successful end state.
    outcome_activities=(
        ("A_Pending", "pending"),
        ("A_Denied", "denied"),
        ("A_Cancelled", "cancelled"),
    ),
)

DEFAULT_DATABASE_URL = "postgresql://localhost:5432/meridian"
DEFAULT_TEST_DATABASE_URL = "postgresql://localhost:5432/meridian_test"

# Pending decision, see 08-OPEN-QUESTIONS.md ("Lifecycle transitions vs. the single-timestamp
# schema"): the normalized log keeps only `complete` transitions until Ved decides otherwise.
DEFAULT_LIFECYCLE_TRANSITIONS: tuple[str, ...] = ("complete",)


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
    database_url: str
    test_database_url: str
    lifecycle_transitions: tuple[str, ...] | None

    @property
    def raw_dir(self) -> Path:
        """Directory for source files exactly as downloaded, never modified in place."""
        return self.data_dir / "raw"

    @property
    def processed_dir(self) -> Path:
        """Directory for normalized and derived outputs, kept apart from raw inputs."""
        return self.data_dir / "processed"

    @property
    def raw_events_csv(self) -> Path:
        """Every parsed event with all lifecycle transitions, before any filtering."""
        return self.processed_dir / "raw_events.csv"

    @property
    def event_log_csv(self) -> Path:
        """The normalized event log that every analytical module reads."""
        return self.processed_dir / "event_log.csv"

    @property
    def ingestion_report_json(self) -> Path:
        """Accounting of the last ingestion run: counts kept, excluded and filtered, by reason."""
        return self.processed_dir / "ingestion_report.json"


def _parse_lifecycle_transitions(value: str | None) -> tuple[str, ...] | None:
    """Parse `MERIDIAN_LIFECYCLE_TRANSITIONS`: comma-separated names, or `all` for no filter.

    Why configurable: which transitions the normalized log keeps is an open question for the
    human (08-OPEN-QUESTIONS.md). Making it a setting means the answer is a re-run, not a rewrite.
    """
    if value is None:
        return DEFAULT_LIFECYCLE_TRANSITIONS
    names = tuple(part.strip().lower() for part in value.split(",") if part.strip())
    if names == ("all",):
        return None
    return names or DEFAULT_LIFECYCLE_TRANSITIONS


def get_settings() -> Settings:
    """Build settings from the environment, falling back to local defaults.

    Why defaults are repo-relative paths and a local database: a stranger who clones the repo
    must be able to run the pipeline with zero configuration (the README's 10-minute requirement).
    """
    data_dir = Path(os.environ.get("MERIDIAN_DATA_DIR", PROJECT_ROOT / "data"))
    return Settings(
        data_dir=data_dir,
        dataset=BPI_2017,
        database_url=os.environ.get("MERIDIAN_DATABASE_URL", DEFAULT_DATABASE_URL),
        test_database_url=os.environ.get("MERIDIAN_TEST_DATABASE_URL", DEFAULT_TEST_DATABASE_URL),
        lifecycle_transitions=_parse_lifecycle_transitions(
            os.environ.get("MERIDIAN_LIFECYCLE_TRANSITIONS")
        ),
    )
