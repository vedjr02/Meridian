"""Shared pytest fixtures: synthetic XES files and an isolated PostgreSQL test database."""

from __future__ import annotations

import dataclasses
import gzip
import hashlib
from collections.abc import Callable, Iterator
from html import escape
from pathlib import Path

import psycopg
import pytest

from meridian.config import DatasetSource, Settings, get_settings

RAW_XML_KEY = "__xml__"


def xes_event(
    activity: str | None,
    lifecycle: str | None = "complete",
    timestamp: str | None = "2016-01-01T09:00:00.000Z",
    resource: str | None = "User_1",
) -> dict[str, str | None]:
    """Build one synthetic event's XES attributes; None omits that attribute from the file."""
    return {
        "concept:name": activity,
        "lifecycle:transition": lifecycle,
        "time:timestamp": timestamp,
        "org:resource": resource,
    }


def _attribute(key: str, value: str) -> str:
    """Render one XES attribute element; timestamps use the `date` type, as real logs do."""
    tag = "date" if key == "time:timestamp" else "string"
    return f'<{tag} key="{escape(key)}" value="{escape(value)}"/>'


def render_xes(traces: list[dict], namespace: str | None = None) -> str:
    """Render traces as an XES document.

    Each trace is `{"case_id": str | None, "events": [...], "case_id_last": bool}`. Each event
    maps XES keys to values; None omits the attribute and the `__xml__` key injects raw XML.
    A log-level attribute and a <global> block are always included so tests prove that neither
    leaks into parsed events.
    """
    xmlns = f' xmlns="{namespace}"' if namespace else ""
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<log xes.version="1849.2016"{xmlns}>',
        '<string key="concept:name" value="Synthetic log"/>',
        '<global scope="event"><string key="concept:name" value="UNKNOWN"/></global>',
    ]
    for trace in traces:
        events = "".join(
            "<event>"
            + "".join(
                value if key == RAW_XML_KEY else _attribute(key, value)
                for key, value in event.items()
                if value is not None
            )
            + "</event>"
            for event in trace["events"]
        )
        case_id = trace.get("case_id")
        case_attribute = "" if case_id is None else _attribute("concept:name", case_id)
        if trace.get("case_id_last"):
            parts.append(f"<trace>{events}{case_attribute}</trace>")
        else:
            parts.append(f"<trace>{case_attribute}{events}</trace>")
    parts.append("</log>")
    return "\n".join(parts)


@pytest.fixture
def write_xes(tmp_path: Path) -> Callable[..., Path]:
    """Return a function that writes synthetic traces to an XES file (optionally gzipped)."""

    def write(
        traces: list[dict],
        *,
        gz: bool = False,
        namespace: str | None = None,
        name: str = "log",
    ) -> Path:
        """Write the rendered XES under tmp_path and return the file's path."""
        content = render_xes(traces, namespace).encode("utf-8")
        path = tmp_path / (f"{name}.xes.gz" if gz else f"{name}.xes")
        path.write_bytes(gzip.compress(content) if gz else content)
        return path

    return write


DISCOVERY_TRACES = [
    {
        "case_id": case_id,
        "events": [
            xes_event(activity, "complete", f"2016-01-0{day}T{hour:02d}:00:00.000Z")
            for hour, activity in enumerate(activities, start=9)
        ],
    }
    for case_id, day, activities in [
        ("c1", 1, ["Submit", "Review", "Approve"]),
        ("c2", 2, ["Submit", "Review", "Approve"]),
        ("c3", 3, ["Submit", "Reject"]),
    ]
]


@pytest.fixture
def discovery_settings(write_xes, tmp_path: Path) -> Settings:
    """Settings for a small synthetic raw log served from a local file:// URL.

    Three cases in two variants (Submit, Review, Approve twice; Submit, Reject once), with
    outcomes, so discovery and API tests exercise every output without network or a database.
    """
    source = write_xes(DISCOVERY_TRACES, gz=True, name="source")
    dataset = DatasetSource(
        name="Synthetic loan log",
        url=source.as_uri(),
        filename="source.xes.gz",
        sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        outcome_activities=(("Approve", "approved"), ("Reject", "rejected")),
    )
    return dataclasses.replace(get_settings(), data_dir=tmp_path / "data", dataset=dataset)


def _drop_meridian_tables(conn: psycopg.Connection) -> None:
    """Remove tables created by ingestion so each test starts from an empty database."""
    conn.execute("DROP TABLE IF EXISTS event_log, ingestion_run")
    conn.commit()


@pytest.fixture
def pg_conn() -> Iterator[psycopg.Connection]:
    """Connect to the dedicated test database, dropping Meridian's tables before and after.

    Why skip instead of fail when PostgreSQL is unreachable: the rest of the suite should still
    run on a machine without a database server, and the skip reason is printed in the `-ra`
    summary so it is never silent. Why compare URLs first: a misconfigured environment must never
    let a test truncate real ingested data.
    """
    settings = get_settings()
    if settings.test_database_url == settings.database_url:
        pytest.fail("MERIDIAN_TEST_DATABASE_URL must differ from MERIDIAN_DATABASE_URL")
    try:
        conn = psycopg.connect(settings.test_database_url, connect_timeout=3)
    except psycopg.OperationalError as exc:
        pytest.skip(f"PostgreSQL test database unavailable: {exc}")
    _drop_meridian_tables(conn)
    try:
        yield conn
    finally:
        conn.rollback()
        _drop_meridian_tables(conn)
        conn.close()
