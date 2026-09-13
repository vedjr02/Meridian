"""Tests for running the DFG step in isolation, on synthetic and (integration) real data."""

import pandas as pd
import pytest
from test_dfg import EXPECTED_EDGES, LOG

from meridian.config import get_settings
from meridian.discovery import dfg as dfg_module
from meridian.discovery.dfg import SOURCE, TARGET, build_dfg
from meridian.ingestion import schema
from meridian.ingestion.io import read_event_log_csv

REAL_EVENT_LOG = get_settings().event_log_csv


def test_cli_writes_edges_and_prints_summary(tmp_path, monkeypatch, capsys) -> None:
    """`python -m meridian.discovery.dfg` must work from ingestion's CSV alone."""
    monkeypatch.setenv("MERIDIAN_DATA_DIR", str(tmp_path))
    settings = get_settings()
    settings.processed_dir.mkdir(parents=True)
    LOG.to_csv(settings.event_log_csv, index=False)

    assert dfg_module.main(["--top", "3"]) == 0

    assert len(pd.read_csv(settings.dfg_edges_csv)) == len(EXPECTED_EDGES)
    output = capsys.readouterr().out
    assert "A -> B: 4 (3 cases), median 22.5min, mean 28.8min" in output


def test_cli_explains_missing_event_log(tmp_path, monkeypatch, capsys) -> None:
    """Without ingestion output, the command must say what to run instead of a traceback."""
    monkeypatch.setenv("MERIDIAN_DATA_DIR", str(tmp_path))

    assert dfg_module.main([]) == 1
    assert "python -m meridian.ingestion" in capsys.readouterr().err


@pytest.mark.integration
@pytest.mark.skipif(not REAL_EVENT_LOG.exists(), reason="run `python -m meridian.ingestion` first")
def test_real_log_dfg_invariants() -> None:
    """On real data, structural identities must hold whatever lifecycle filter was used.

    Every case contributes events minus one transition, exactly one start and one end activity,
    and no edge may reference an activity that has no events.
    """
    log = read_event_log_csv(REAL_EVENT_LOG)

    dfg = build_dfg(log)

    assert dfg.transition_count == len(log) - log[schema.CASE_ID].nunique()
    assert sum(dfg.start_activities.values()) == dfg.case_count
    assert sum(dfg.end_activities.values()) == dfg.case_count
    assert set(dfg.edges[SOURCE]) | set(dfg.edges[TARGET]) <= set(dfg.activity_counts)
