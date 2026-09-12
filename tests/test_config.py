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
