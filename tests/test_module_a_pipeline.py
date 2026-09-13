"""Module A run as a user runs it: the miner command, and raw XES to mined model on real data."""

import dataclasses
import json

import pytest
from test_heuristic_net import EXPECTED, LOG

from meridian.config import get_settings
from meridian.discovery import heuristic_miner
from meridian.discovery.dfg import SOURCE, TARGET, build_dfg
from meridian.discovery.heuristic_miner import LENGTH_TWO_LOOP, mine_heuristic_net
from meridian.ingestion import schema
from meridian.ingestion.io import read_event_log_csv
from meridian.ingestion.pipeline import run_ingestion

REAL_SETTINGS = get_settings()
REAL_LOG = REAL_SETTINGS.raw_dir / REAL_SETTINGS.dataset.filename


def _write_synthetic_event_log(tmp_path, monkeypatch):
    """Point settings at tmp_path and place the loop test log where ingestion would write it."""
    monkeypatch.setenv("MERIDIAN_DATA_DIR", str(tmp_path))
    settings = get_settings()
    settings.processed_dir.mkdir(parents=True)
    LOG.to_csv(settings.event_log_csv, index=False)
    return settings


def test_miner_command_writes_model_and_summary(tmp_path, monkeypatch, capsys) -> None:
    """`python -m meridian.discovery.heuristic_miner` works from ingestion's CSV alone."""
    settings = _write_synthetic_event_log(tmp_path, monkeypatch)

    assert heuristic_miner.main([]) == 0

    model = json.loads(settings.heuristic_net_json.read_text())
    assert len(model["edges"]) == len(EXPECTED)
    output = capsys.readouterr().out
    assert "length_two_loop 2" in output
    assert "Orphan activities: none" in output


def test_miner_command_rejects_unusable_threshold(tmp_path, monkeypatch, capsys) -> None:
    """A threshold of 1 would silently produce an empty model, so the command refuses it."""
    _write_synthetic_event_log(tmp_path, monkeypatch)

    assert heuristic_miner.main(["--threshold", "1"]) == 2
    assert "strictly between 0 and 1" in capsys.readouterr().err


def test_miner_command_explains_missing_event_log(tmp_path, monkeypatch, capsys) -> None:
    """Without ingestion output the command says what to run, rather than raising."""
    monkeypatch.setenv("MERIDIAN_DATA_DIR", str(tmp_path))

    assert heuristic_miner.main([]) == 1
    assert "python -m meridian.ingestion" in capsys.readouterr().err


@pytest.mark.integration
@pytest.mark.skipif(not REAL_LOG.exists(), reason="run `python -m meridian.datasets` first")
def test_module_a_end_to_end_on_real_log_is_plausible(tmp_path) -> None:
    """Raw BPI 2017 XES to mined model, with the plausibility checks from 04-BUILD-PLAN Day 5.

    Checks: every parsed event is accounted for; the DFG identity holds on what ingestion wrote;
    no orphan activities; the single start activity is the application's creation, which nothing
    precedes; every edge joins known activities; and the known offer loop is a loop, not
    parallelism. Values tied to the lifecycle choice (08-OPEN-QUESTIONS.md) are not pinned here.
    """
    (tmp_path / "raw").mkdir()
    (tmp_path / "raw" / REAL_SETTINGS.dataset.filename).symlink_to(REAL_LOG)
    settings = dataclasses.replace(REAL_SETTINGS, data_dir=tmp_path)

    ingestion = run_ingestion(settings, load_database=False)
    event_log = read_event_log_csv(settings.event_log_csv)
    dfg = build_dfg(event_log)
    net = mine_heuristic_net(event_log, settings.dependency_threshold)

    assert ingestion.report.is_fully_accounted
    assert len(event_log) == ingestion.report.normalized_events
    assert dfg.transition_count == len(event_log) - event_log[schema.CASE_ID].nunique()

    assert net.orphan_activities == []
    assert net.start_activities == {"A_Create Application": ingestion.report.normalized_cases}
    assert "A_Create Application" not in set(net.edges[TARGET])
    assert sum(net.end_activities.values()) == net.case_count
    assert set(net.edges[SOURCE]) | set(net.edges[TARGET]) <= set(net.activities)

    kinds = {(e.source, e.target): e.kind for e in net.edges.itertuples()}
    assert kinds[("O_Create Offer", "O_Created")] == LENGTH_TWO_LOOP
    assert kinds[("O_Created", "O_Create Offer")] == LENGTH_TWO_LOOP
