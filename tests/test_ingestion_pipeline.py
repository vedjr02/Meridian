"""End-to-end ingestion tests: a synthetic log through every step, and the real BPI 2017 log."""

import dataclasses
import hashlib
import json

import pandas as pd
import pytest
from conftest import xes_event

from meridian.config import DatasetSource, Settings, get_settings
from meridian.ingestion import pipeline
from meridian.ingestion.pipeline import run_ingestion

TRACES = [
    {
        "case_id": "c1",
        "events": [
            xes_event("Submit", "complete", "2016-01-01T09:00:00.000Z"),
            xes_event("Review", "start", "2016-01-01T10:00:00.000Z"),
            xes_event("Review", "complete", "2016-01-01T11:00:00.000Z"),
            xes_event("Approve", "complete", "2016-01-01T12:00:00.000Z"),
        ],
    },
    {
        "case_id": "c2",
        "events": [
            xes_event("Submit", "complete", "2016-01-02T09:00:00.000Z"),
            xes_event("Check", "complete", None),
        ],
    },
]

REAL_SETTINGS = get_settings()
REAL_LOG = REAL_SETTINGS.raw_dir / REAL_SETTINGS.dataset.filename


@pytest.fixture
def synthetic_settings(write_xes, tmp_path) -> Settings:
    """Settings for a synthetic gzipped log served from a local file:// URL (no network)."""
    source_file = write_xes(TRACES, gz=True, name="synthetic")
    dataset = DatasetSource(
        name="synthetic",
        url=source_file.as_uri(),
        filename="synthetic.xes.gz",
        sha256=hashlib.sha256(source_file.read_bytes()).hexdigest(),
        outcome_activities=(("Approve", "approved"),),
    )
    return dataclasses.replace(
        get_settings(),
        data_dir=tmp_path / "data",
        dataset=dataset,
        lifecycle_transitions=("complete",),
    )


def test_pipeline_writes_reconciled_outputs_without_database(synthetic_settings) -> None:
    """Every output file agrees with the report, and the report accounts for every event."""
    result = run_ingestion(synthetic_settings, load_database=False)

    report = result.report
    assert result.source_events == report.parsed_events == 6
    assert report.normalized_events == 4
    assert report.filtered_by_lifecycle == 1
    assert report.excluded["missing_timestamp"] == 1
    assert result.run_id is None
    assert len(pd.read_csv(synthetic_settings.event_log_csv)) == report.normalized_events
    assert len(pd.read_csv(synthetic_settings.raw_events_csv)) == result.source_events
    payload = json.loads(synthetic_settings.ingestion_report_json.read_text())
    assert payload["source"]["event_elements"] == 6
    assert payload["normalization"]["is_fully_accounted"] is True


def test_pipeline_loads_postgres_with_matching_row_count(synthetic_settings, pg_conn) -> None:
    """With a database configured, the run is stored and the table matches the normalized log."""
    settings = dataclasses.replace(
        synthetic_settings, database_url=synthetic_settings.test_database_url
    )

    result = run_ingestion(settings, load_database=True)

    assert result.run_id is not None
    stored = pg_conn.execute("SELECT count(*) FROM event_log").fetchone()[0]
    assert stored == result.report.normalized_events


def test_cli_prints_every_count_and_exits_zero(synthetic_settings, monkeypatch, capsys) -> None:
    """The command a stranger runs must succeed and show every count, including zero exclusions."""
    monkeypatch.setattr(pipeline, "get_settings", lambda: synthetic_settings)

    assert pipeline.main(["--no-db"]) == 0

    output = capsys.readouterr().out
    assert "Normalized events:" in output
    assert "out_of_order: 0" in output


def test_cli_stops_on_checksum_failure_without_writing_outputs(
    synthetic_settings, monkeypatch
) -> None:
    """A changed or corrupted source must stop ingestion with exit code 1 and no partial output."""
    wrong_checksum = dataclasses.replace(synthetic_settings.dataset, sha256="0" * 64)
    settings = dataclasses.replace(synthetic_settings, dataset=wrong_checksum)
    monkeypatch.setattr(pipeline, "get_settings", lambda: settings)

    assert pipeline.main(["--no-db"]) == 1
    assert not settings.event_log_csv.exists()


@pytest.mark.integration
@pytest.mark.skipif(not REAL_LOG.exists(), reason="run `python -m meridian.datasets` first")
def test_real_bpi_2017_log_reconciles_end_to_end(tmp_path, pg_conn) -> None:
    """On the real log, every count reconciles from source file to database.

    31,509 cases and 1,202,267 events are the published size of BPI Challenge 2017. The other
    expected values were measured when the raw log was first profiled (Day 2), so any change in
    parsing or normalization behaviour on real data fails this test.
    """
    (tmp_path / "raw").mkdir()
    (tmp_path / "raw" / REAL_SETTINGS.dataset.filename).symlink_to(REAL_LOG)
    settings = dataclasses.replace(
        REAL_SETTINGS, data_dir=tmp_path, database_url=REAL_SETTINGS.test_database_url
    )

    result = run_ingestion(settings, load_database=True)

    report = result.report
    assert result.source_events == report.parsed_events == 1_202_267
    assert report.parsed_cases == report.normalized_cases == 31_509
    assert report.is_fully_accounted
    assert report.total_excluded == 0
    assert report.normalized_events == 475_306
    assert report.filtered_by_lifecycle == 1_202_267 - 475_306
    assert report.events_missing_resource == 0
    assert report.outcome_counts == {
        "pending": 17_228,
        "cancelled": 10_431,
        "denied": 3_752,
        "no_terminal_state": 98,
    }
    assert pg_conn.execute("SELECT count(*) FROM event_log").fetchone()[0] == 475_306
