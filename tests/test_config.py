"""Tests for central configuration."""

from pathlib import Path

from meridian.config import PROJECT_ROOT, get_settings


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


def test_lifecycle_transitions_are_configurable_from_env(monkeypatch) -> None:
    """The open lifecycle decision must be switchable by environment, not by editing code."""
    monkeypatch.setenv("MERIDIAN_LIFECYCLE_TRANSITIONS", "Complete, start")
    assert get_settings().lifecycle_transitions == ("complete", "start")

    monkeypatch.setenv("MERIDIAN_LIFECYCLE_TRANSITIONS", "all")
    assert get_settings().lifecycle_transitions is None

    monkeypatch.delenv("MERIDIAN_LIFECYCLE_TRANSITIONS")
    assert get_settings().lifecycle_transitions == ("complete",)
