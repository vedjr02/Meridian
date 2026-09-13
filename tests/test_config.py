"""Tests for central configuration."""

from pathlib import Path

import pytest

from meridian.config import PROJECT_ROOT, get_settings
from meridian.ingestion.lifecycle import LifecyclePolicy


def test_default_data_dir_is_repo_relative(monkeypatch) -> None:
    """With no environment set, a fresh clone must find `data/` without any configuration."""
    monkeypatch.delenv("MERIDIAN_DATA_DIR", raising=False)

    settings = get_settings()

    assert settings.data_dir == PROJECT_ROOT / "data"
    assert settings.raw_dir == PROJECT_ROOT / "data" / "raw"


def test_data_dir_env_override(monkeypatch, tmp_path: Path) -> None:
    """Tests and other machines relocate data via the environment, never by editing code."""
    monkeypatch.setenv("MERIDIAN_DATA_DIR", str(tmp_path))

    settings = get_settings()

    assert settings.raw_dir == tmp_path / "raw"
    assert settings.processed_dir == tmp_path / "processed"
    assert settings.event_log_csv.parent == tmp_path / "processed"


def test_database_urls_default_to_separate_local_databases(monkeypatch) -> None:
    """Tests must never share a database with real runs, or a test could wipe ingested data."""
    monkeypatch.delenv("MERIDIAN_DATABASE_URL", raising=False)
    monkeypatch.delenv("MERIDIAN_TEST_DATABASE_URL", raising=False)

    settings = get_settings()

    assert settings.database_url.endswith("/meridian")
    assert settings.test_database_url.endswith("/meridian_test")


def test_lifecycle_policy_defaults_to_the_decision_and_is_configurable(monkeypatch) -> None:
    """Default is Ved's decision (start where recorded); comparisons are an env change, not code."""
    monkeypatch.delenv("MERIDIAN_LIFECYCLE_POLICY", raising=False)
    assert get_settings().lifecycle_policy is LifecyclePolicy.START_ELSE_COMPLETE

    monkeypatch.setenv("MERIDIAN_LIFECYCLE_POLICY", " Complete ")
    assert get_settings().lifecycle_policy is LifecyclePolicy.COMPLETE

    monkeypatch.setenv("MERIDIAN_LIFECYCLE_POLICY", "sometimes")
    with pytest.raises(ValueError, match="start_else_complete, complete, all"):
        get_settings()


def test_dependency_threshold_defaults_and_env_override(monkeypatch) -> None:
    """The miner's threshold is tunable per run (02-TECH-STACK: configurable, not hardcoded)."""
    monkeypatch.delenv("MERIDIAN_DEPENDENCY_THRESHOLD", raising=False)
    assert get_settings().dependency_threshold == 0.9

    monkeypatch.setenv("MERIDIAN_DEPENDENCY_THRESHOLD", "0.75")
    assert get_settings().dependency_threshold == 0.75


@pytest.mark.parametrize("value", ["0", "1", "1.5", "-0.2"])
def test_unusable_dependency_threshold_is_rejected(monkeypatch, value: str) -> None:
    """A threshold of 1 silently yields no edges and 0 accepts no-evidence pairs; both must fail."""
    monkeypatch.setenv("MERIDIAN_DEPENDENCY_THRESHOLD", value)

    with pytest.raises(ValueError, match="strictly between 0 and 1"):
        get_settings()
