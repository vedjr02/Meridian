"""Tests for replaying a whole log: per-case rows, pooled log fitness and the deviation share."""

import pytest
from test_heuristic_miner import log_from_variants

from meridian.conformance import replay as replay_module
from meridian.conformance.petri_net import sequence_net
from meridian.conformance.replay import (
    CASE_REPLAY_COLUMNS,
    FITNESS,
    replay_log,
    replay_trace,
)
from meridian.ingestion import schema

NET = sequence_net(["A", "B", "C", "D"])

# Two perfect cases (5, 5, 0, 0 each) and one that skips C (4, 4, 1, 1).
LOG = log_from_variants({("A", "B", "C", "D"): 2, ("A", "B", "D"): 1})


def test_each_case_row_matches_single_trace_replay() -> None:
    """Log-level replay must give every case exactly what replaying it alone gives."""
    result = replay_log(LOG, NET)

    assert tuple(result.cases.columns) == CASE_REPLAY_COLUMNS
    assert result.case_count == 3
    sequences = (
        LOG.sort_values([schema.CASE_ID, schema.EVENT_INDEX])
        .groupby(schema.CASE_ID)[schema.ACTIVITY]
        .agg(tuple)
    )
    for row in result.cases.itertuples(index=False):
        expected = replay_trace(NET, sequences[row.case_id])
        assert (row.missing, row.remaining, row.fitness) == (
            expected.missing,
            expected.remaining,
            expected.fitness,
        )


def test_aggregates_are_hand_computed() -> None:
    """Pooled m = 1, c = 14, r = 1, p = 14: log fitness 1 - 1/14; case mean (1 + 1 + 0.75) / 3."""
    result = replay_log(LOG, NET)

    assert result.fitting_cases == 2
    assert result.deviating_share == pytest.approx(1 / 3)
    assert result.log_fitness == pytest.approx(1 - 1 / 14)
    summary = result.case_fitness_summary()
    assert summary["mean"] == pytest.approx(2.75 / 3)
    assert summary["p50"] == 1.0


def test_identical_sequences_are_replayed_once(monkeypatch) -> None:
    """Replay depends only on the sequence, so 3 cases with 2 distinct sequences need 2 replays."""
    calls = []
    original = replay_module.replay_trace

    def counting_replay(net, trace):
        """Record each replay, then delegate to the real implementation."""
        calls.append(tuple(trace))
        return original(net, trace)

    monkeypatch.setattr(replay_module, "replay_trace", counting_replay)

    result = replay_log(LOG, NET)

    assert len(calls) == 2
    assert result.cases[FITNESS].tolist().count(1.0) == 2


def test_empty_log_is_rejected() -> None:
    """Aggregate fitness of no cases is undefined; it must fail instead of dividing by zero."""
    with pytest.raises(ValueError, match="empty event log"):
        replay_log(LOG.iloc[0:0], NET)
