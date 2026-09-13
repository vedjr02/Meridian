"""Reading the normalized event log back from its CSV file with the schema's types restored."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from meridian.ingestion import schema

_TEXT_COLUMNS = (schema.CASE_ID, schema.ACTIVITY, schema.RESOURCE, schema.OUTCOME)


def read_event_log_csv(path: Path) -> pd.DataFrame:
    """Load a normalized `event_log.csv` with correct column types.

    Why explicit types: CSV carries none. Left to inference, pandas would read numeric-looking case
    ids (common in other BPI logs) as integers and timestamps as plain strings, and a downstream
    module would then sort or join on the wrong type without any error.

    Why only empty cells count as missing: pandas treats strings such as "NA" or "null" as missing
    by default, which would silently erase any activity or resource that happens to have that name.
    Ingestion writes missing values as empty cells, so that is the only marker honoured here.
    """
    dtypes = {name: "string" for name in _TEXT_COLUMNS} | {
        schema.EVENT_INDEX: "int64",
        schema.COST: "float64",
    }
    frame = pd.read_csv(path, dtype=dtypes, keep_default_na=False, na_values=[""])
    frame[schema.TIMESTAMP] = pd.to_datetime(frame[schema.TIMESTAMP], utc=True, format="ISO8601")
    return frame.loc[:, list(schema.NORMALIZED_COLUMNS)]
