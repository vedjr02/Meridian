"""Module A acceptance: one command from raw log to map, model, variant table and summary."""

import dataclasses
import json

import pandas as pd
import pytest

from meridian.config import Settings, get_settings
from meridian.discovery import pipeline
from meridian.discovery.pipeline import run_discovery
from meridian.ingestion.lifecycle import LifecyclePolicy

REAL_SETTINGS = get_settings()
REAL_LOG = REAL_SETTINGS.raw_dir / REAL_SETTINGS.dataset.filename


@pytest.fixture
def settings(discovery_settings: Settings) -> Settings:
    """The shared synthetic raw log from conftest (three cases, two variants)."""
    return discovery_settings


def test_one_command_produces_every_acceptance_output(settings) -> None:
    """From raw XES: (a) Mermaid DFG, (b) model JSON, (c) variant table, (d) written summary."""
    result = run_discovery(settings, load_database=False)

    assert result.ingested
    assert all(path.exists() for path in result.outputs.values())
    assert settings.dfg_mermaid.read_text().startswith("flowchart LR")
    assert json.loads(settings.heuristic_net_json.read_text())["case_count"] == 3
    variants = pd.read_csv(settings.variants_csv)
    assert variants["case_count"].tolist() == [2, 1]
    summary = settings.discovery_summary_md.read_text()
    assert summary.startswith("# Process discovery summary — Synthetic loan log")
    assert "Covering 80% of cases takes 2 of 2 distinct variants" in summary
    assert "| All cases | 3 |" in summary
    assert "(lifecycle rule: start where recorded, otherwise complete)" in summary


def test_existing_normalized_log_is_reused_without_reingesting(settings, monkeypatch) -> None:
    """Threshold experiments re-run discovery in seconds; ingestion must not run again."""
    run_discovery(settings, load_database=False)

    def ingestion_must_not_run(*args, **kwargs):
        """Fail loudly if discovery tries to ingest again."""
        raise AssertionError("ingestion ran although a normalized log exists")

    monkeypatch.setattr(pipeline, "run_ingestion", ingestion_must_not_run)

    assert run_discovery(settings, load_database=False).ingested is False


def test_recorded_lifecycle_policy_reads_what_ingestion_recorded(settings) -> None:
    """Summaries describe the data on disk, and know when no ingestion report exists."""
    assert pipeline.recorded_lifecycle_policy(settings) is None

    run_discovery(settings, load_database=False)

    assert pipeline.recorded_lifecycle_policy(settings) is LifecyclePolicy.START_ELSE_COMPLETE


def test_command_prints_headline_and_output_paths(settings, monkeypatch, capsys) -> None:
    """`python -m meridian.discovery --no-db` exits 0 and tells the user where everything is."""
    monkeypatch.setattr(pipeline, "get_settings", lambda: settings)

    assert pipeline.main(["--no-db"]) == 0

    output = capsys.readouterr().out
    assert "Variants covering 80% of cases: 2" in output
    assert "Written summary:" in output


@pytest.mark.integration
@pytest.mark.skipif(not REAL_LOG.exists(), reason="run `python -m meridian.datasets` first")
def test_module_a_acceptance_on_real_log(tmp_path) -> None:
    """The acceptance command on BPI 2017, checked for internal consistency across outputs."""
    (tmp_path / "raw").mkdir()
    (tmp_path / "raw" / REAL_SETTINGS.dataset.filename).symlink_to(REAL_LOG)
    settings = dataclasses.replace(REAL_SETTINGS, data_dir=tmp_path)

    result = run_discovery(settings, load_database=False)

    assert result.case_count == 31_509
    assert all(path.exists() for path in result.outputs.values())
    variants = pd.read_csv(settings.variants_csv)
    assert len(variants) == result.variant_count
    assert int(variants["case_count"].sum()) == result.case_count
    summary = settings.discovery_summary_md.read_text()
    assert f"takes {result.variants_to_cover:,} of {result.variant_count:,} distinct" in summary
    assert "| All cases | 31,509 |" in summary
    assert "```mermaid" in summary
    assert json.loads(settings.heuristic_net_json.read_text())["start_activities"] == {
        "A_Create Application": 31_509
    }
