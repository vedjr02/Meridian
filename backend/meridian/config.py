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

from meridian.ingestion.lifecycle import LifecyclePolicy

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

# Decided by Ved on 2026-09-13 (08-OPEN-QUESTIONS.md): represent activities by their start events
# where the log records them, otherwise by completion. Complete-only undercounts W_ work by ~99%.
DEFAULT_LIFECYCLE_POLICY = LifecyclePolicy.START_ELSE_COMPLETE

# Heuristic Miner dependency threshold: a pair A->B becomes a causal edge when
# (|A>B| - |B>A|) / (|A>B| + |B>A| + 1) reaches this value. 0.9 is the common default
# (02-TECH-STACK-AND-SKILLS.md). What it means in counts: with no reverse observations a pair
# needs |A>B| >= 9 to qualify (n / (n + 1) >= 0.9), and each reverse observation raises the bar,
# e.g. 50 forward against 1 backward gives 49 / 52 = 0.94 and still qualifies. On BPI 2017's
# 31,509 cases, 9 observations is a permissive floor, so the value is revisited against the real
# log when the full model is run on Day 5; any change and its reason go in 07-PROGRESS-STATE.md.
DEFAULT_DEPENDENCY_THRESHOLD = 0.9


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
    lifecycle_policy: LifecyclePolicy
    dependency_threshold: float = DEFAULT_DEPENDENCY_THRESHOLD

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
    def dfg_edges_csv(self) -> Path:
        """Directly-follows graph edges: frequency and duration per activity-to-activity pair."""
        return self.processed_dir / "dfg_edges.csv"

    @property
    def dfg_mermaid(self) -> Path:
        """Mermaid flowchart of the most frequent DFG edges (renders on GitHub and in editors)."""
        return self.processed_dir / "dfg.mmd"

    @property
    def heuristic_net_json(self) -> Path:
        """The mined heuristic process model: start/end activities, causal and loop edges."""
        return self.processed_dir / "heuristic_net.json"

    @property
    def variants_csv(self) -> Path:
        """Variant frequency table: every distinct path with case count and cumulative share."""
        return self.processed_dir / "variants.csv"

    @property
    def case_statistics_csv(self) -> Path:
        """Per-case cycle time, activity count, variant rank, happy-path flag and outcome."""
        return self.processed_dir / "case_statistics.csv"

    @property
    def discovery_summary_md(self) -> Path:
        """Written Module A summary: variants, cycle-time distribution, process map, caveats."""
        return self.processed_dir / "discovery_summary.md"

    @property
    def conformance_cases_csv(self) -> Path:
        """Per-case token-replay counts and fitness against the stated reference model."""
        return self.processed_dir / "conformance_cases.csv"

    @property
    def conformance_summary_json(self) -> Path:
        """Reference model used, how it was chosen, and log-level conformance aggregates."""
        return self.processed_dir / "conformance_summary.json"

    @property
    def bottlenecks_csv(self) -> Path:
        """Per-transition wait-time distribution, aggregate time and bottleneck classification."""
        return self.processed_dir / "bottlenecks.csv"

    @property
    def rework_cases_csv(self) -> Path:
        """Per-case rework events, repeated activities and cycle time inside rework loops."""
        return self.processed_dir / "rework_cases.csv"

    @property
    def rework_activities_csv(self) -> Path:
        """Per-activity rework: affected cases, repetitions and time spans."""
        return self.processed_dir / "rework_activities.csv"

    @property
    def diagnostic_report_md(self) -> Path:
        """Written Module B report answering the three diagnostic questions with numbers."""
        return self.processed_dir / "diagnostic_report.md"

    @property
    def ingestion_report_json(self) -> Path:
        """Accounting of the last ingestion run: counts kept, excluded and filtered, by reason."""
        return self.processed_dir / "ingestion_report.json"


def _parse_lifecycle_policy(value: str | None) -> LifecyclePolicy:
    """Parse `MERIDIAN_LIFECYCLE_POLICY`, rejecting unknown values with the allowed list.

    Why still configurable after the decision: comparing policies on the same data (for example
    to show how much complete-only undercounts) should be a re-run, not a code change.
    """
    if value is None or not value.strip():
        return DEFAULT_LIFECYCLE_POLICY
    try:
        return LifecyclePolicy(value.strip().lower())
    except ValueError:
        allowed = ", ".join(policy.value for policy in LifecyclePolicy)
        raise ValueError(
            f"MERIDIAN_LIFECYCLE_POLICY must be one of: {allowed}; got {value!r}"
        ) from None


def validate_dependency_threshold(value: float) -> float:
    """Return `value` if it is a usable dependency threshold, else raise ValueError.

    Why the open interval (0, 1): the dependency measure is always strictly below 1 (the +1 in its
    denominator), so a threshold of 1 or more silently yields a model with no edges, and a
    threshold of 0 or less would accept pairs with no directional evidence at all.
    """
    if not 0 < value < 1:
        raise ValueError(f"Dependency threshold must be strictly between 0 and 1, got {value}")
    return value


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
        lifecycle_policy=_parse_lifecycle_policy(os.environ.get("MERIDIAN_LIFECYCLE_POLICY")),
        dependency_threshold=validate_dependency_threshold(
            float(os.environ.get("MERIDIAN_DEPENDENCY_THRESHOLD", DEFAULT_DEPENDENCY_THRESHOLD))
        ),
    )
