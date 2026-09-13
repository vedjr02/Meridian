"""Tests for PostgreSQL storage of the normalized event log.

These use the dedicated test database from the `pg_conn` fixture and are skipped, with the
reason shown in the pytest summary, when PostgreSQL is not reachable.
"""

import pandas as pd
import psycopg
import pytest

from meridian.ingestion import schema
from meridian.ingestion.normalize import normalize_events
from meridian.ingestion.store import read_event_log, replace_event_log

ROWS = [
    ("c1", 0, "Submit", "complete", "2016-01-01T09:00:00.123Z", "User_1"),
    ("c1", 1, "Approve", "complete", "2016-01-01T12:00:00.000Z", None),
    ("c2", 0, "Submit", "complete", "2016-01-02T09:00:00.000Z", "User_1"),
]
REPORT = {"normalization": {"normalized_events": 3}}


def _event_log() -> pd.DataFrame:
    """A small normalized log with a NULL resource, a NULL outcome and sub-second timestamps."""
    raw = pd.DataFrame(ROWS, columns=list(schema.RAW_COLUMNS))
    return normalize_events(raw, outcome_activities={"Approve": "approved"})[0]


def _load(conn: psycopg.Connection, event_log: pd.DataFrame) -> int:
    """Load an event log with fixed source metadata, returning the ingestion run id."""
    return replace_event_log(
        conn, event_log, source_filename="log.xes", source_sha256="ab" * 32, report=REPORT
    )


def _records(frame: pd.DataFrame) -> list[tuple]:
    """Rows as comparable Python values, with every kind of missing value turned into None."""
    return [
        tuple(None if pd.isna(value) else value for value in row)
        for row in frame.itertuples(index=False, name=None)
    ]


def test_round_trip_preserves_rows_values_and_nulls(pg_conn) -> None:
    """What modules read back from the database must be exactly what ingestion produced."""
    event_log = _event_log()

    _load(pg_conn, event_log)

    assert _records(read_event_log(pg_conn)) == _records(event_log)


def test_reloading_replaces_rather_than_appends(pg_conn) -> None:
    """Re-running ingestion must be idempotent; appending would silently double every event."""
    event_log = _event_log()

    _load(pg_conn, event_log)
    _load(pg_conn, event_log)

    assert pg_conn.execute("SELECT count(*) FROM event_log").fetchone()[0] == len(event_log)


def test_each_run_is_recorded_with_its_report(pg_conn) -> None:
    """`ingestion_run` is the audit trail of what was loaded, from which file, with what counts."""
    run_id = _load(pg_conn, _event_log())

    filename, report = pg_conn.execute(
        "SELECT source_filename, report FROM ingestion_run WHERE run_id = %s", (run_id,)
    ).fetchone()

    assert filename == "log.xes"
    assert report == REPORT


def test_failed_load_rolls_back_and_keeps_previous_data(pg_conn) -> None:
    """A load that fails midway (a duplicate key here) must not leave a truncated table behind."""
    good = _event_log()
    _load(pg_conn, good)
    duplicated_row = pd.concat([good, good.iloc[[0]]], ignore_index=True)

    with pytest.raises(psycopg.errors.UniqueViolation):
        _load(pg_conn, duplicated_row)

    assert pg_conn.execute("SELECT count(*) FROM event_log").fetchone()[0] == len(good)
