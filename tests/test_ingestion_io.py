"""Tests for reading the normalized event log CSV back with correct types."""

import pandas as pd

from meridian.ingestion import schema
from meridian.ingestion.io import read_event_log_csv
from meridian.ingestion.normalize import normalize_events

ROWS = [
    ("1001", 0, "Submit", "complete", "2016-01-01T09:00:00.123+01:00", "User_1"),
    ("1001", 1, "NA", "complete", "2016-01-01T12:00:00.000Z", None),
    ("1002", 0, "Submit", "complete", "2016-01-02T09:00:00.000Z", "null"),
]


def _normalized() -> pd.DataFrame:
    """A normalized log with numeric-looking case ids, "NA"/"null" labels and a missing resource."""
    raw = pd.DataFrame(ROWS, columns=list(schema.RAW_COLUMNS))
    return normalize_events(raw, outcome_activities={"NA": "done"})[0]


def test_csv_round_trip_preserves_values_and_types(tmp_path) -> None:
    """Modules reading the CSV must see exactly what ingestion wrote, with the same types."""
    event_log = _normalized()
    path = tmp_path / "event_log.csv"
    event_log.to_csv(path, index=False)

    loaded = read_event_log_csv(path)

    assert tuple(loaded.columns) == schema.NORMALIZED_COLUMNS
    assert loaded[schema.CASE_ID].tolist() == ["1001", "1001", "1002"]
    assert str(loaded[schema.TIMESTAMP].dt.tz) == "UTC"
    assert loaded.loc[0, schema.TIMESTAMP] == pd.Timestamp("2016-01-01T08:00:00.123Z")
    assert loaded[schema.EVENT_INDEX].dtype == "int64"


def test_only_empty_cells_are_treated_as_missing(tmp_path) -> None:
    """An activity called "NA" or a resource called "null" must survive; a blank must not."""
    path = tmp_path / "event_log.csv"
    _normalized().to_csv(path, index=False)

    loaded = read_event_log_csv(path)

    assert loaded.loc[1, schema.ACTIVITY] == "NA"
    assert loaded.loc[2, schema.RESOURCE] == "null"
    assert pd.isna(loaded.loc[1, schema.RESOURCE])
    assert loaded.loc[0, schema.OUTCOME] == "done"
