"""PostgreSQL persistence for the normalized event log and the ingestion audit trail."""

from __future__ import annotations

from collections.abc import Iterator

import pandas as pd
import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb

from meridian.ingestion import schema

_CREATE_EVENT_LOG = """
CREATE TABLE IF NOT EXISTS event_log (
    case_id     TEXT             NOT NULL,
    event_index INTEGER          NOT NULL,
    activity    TEXT             NOT NULL,
    timestamp   TIMESTAMPTZ      NOT NULL,
    resource    TEXT,
    cost        DOUBLE PRECISION,
    outcome     TEXT,
    PRIMARY KEY (case_id, event_index)
)
"""

_CREATE_INGESTION_RUN = """
CREATE TABLE IF NOT EXISTS ingestion_run (
    run_id          BIGSERIAL   PRIMARY KEY,
    ingested_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    source_filename TEXT        NOT NULL,
    source_sha256   TEXT        NOT NULL,
    report          JSONB       NOT NULL
)
"""

_COLUMNS = sql.SQL(", ").join(sql.Identifier(name) for name in schema.NORMALIZED_COLUMNS)


class StoredRowCountMismatchError(RuntimeError):
    """Raised when the database holds a different number of rows than were sent to it.

    A dedicated type so the pipeline can report "rows lost on the way into storage" distinctly
    from parsing or normalization failures.
    """


def ensure_schema(conn: psycopg.Connection) -> None:
    """Create the event-log tables if they do not exist.

    Why plain `IF NOT EXISTS` DDL instead of a migration tool: there are two tables and no schema
    history yet; a migration framework would be a new major dependency with no current benefit.
    Revisit once the schema starts changing between runs.
    """
    conn.execute(_CREATE_EVENT_LOG)
    conn.execute(_CREATE_INGESTION_RUN)


def _database_rows(event_log: pd.DataFrame) -> Iterator[tuple]:
    """Yield event-log rows as plain Python values, with None for every missing value.

    Why: pandas missing markers (NaN, NA, NaT) and numpy scalars are not database values; COPY
    needs None for NULL and native ints, floats and datetimes.
    """
    frame = event_log.loc[:, list(schema.NORMALIZED_COLUMNS)].astype(object)
    frame = frame.where(frame.notna(), None)
    for row in frame.itertuples(index=False, name=None):
        yield tuple(
            value.to_pydatetime() if isinstance(value, pd.Timestamp) else value for value in row
        )


def replace_event_log(
    conn: psycopg.Connection,
    event_log: pd.DataFrame,
    *,
    source_filename: str,
    source_sha256: str,
    report: dict,
) -> int:
    """Atomically replace the stored event log, record the ingestion run, and return its id.

    Why replace (TRUNCATE + COPY) rather than append: the project analyses one static log in batch
    (01-REQUIREMENTS.md scope), so re-running ingestion must be idempotent; appending would
    silently duplicate every event. Doing it in one transaction means no reader ever sees a
    half-loaded table, and a failed load leaves the previous data intact.

    Why the row count is re-checked inside the transaction: it is the last hand-off where rows
    could be lost, and failing here rolls the whole load back instead of committing a short table.
    """
    with conn.transaction():
        ensure_schema(conn)
        with conn.cursor() as cursor:
            cursor.execute("TRUNCATE event_log")
            copy_statement = sql.SQL("COPY event_log ({}) FROM STDIN").format(_COLUMNS)
            with cursor.copy(copy_statement) as copy:
                for row in _database_rows(event_log):
                    copy.write_row(row)

            stored = cursor.execute("SELECT count(*) FROM event_log").fetchone()[0]
            if stored != len(event_log):
                raise StoredRowCountMismatchError(
                    f"Sent {len(event_log)} events to PostgreSQL but event_log holds {stored}."
                )

            run_id = cursor.execute(
                "INSERT INTO ingestion_run (source_filename, source_sha256, report) "
                "VALUES (%s, %s, %s) RETURNING run_id",
                (source_filename, source_sha256, Jsonb(report)),
            ).fetchone()[0]
    return run_id


def read_event_log(conn: psycopg.Connection) -> pd.DataFrame:
    """Load the stored event log in canonical order: by case, then position in the source trace.

    Why the ORDER BY is explicit: SQL tables are unordered, and directly-follows computation
    depends on event order, so the order is part of this function's contract rather than an
    accident of how rows happened to be stored.
    """
    query = sql.SQL("SELECT {} FROM event_log ORDER BY case_id, event_index").format(_COLUMNS)
    with conn.cursor() as cursor:
        rows = cursor.execute(query).fetchall()
    frame = pd.DataFrame(rows, columns=list(schema.NORMALIZED_COLUMNS))
    frame[schema.TIMESTAMP] = pd.to_datetime(frame[schema.TIMESTAMP], utc=True)
    frame[schema.COST] = pd.to_numeric(frame[schema.COST])
    return frame
