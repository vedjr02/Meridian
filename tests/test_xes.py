"""Tests for the streaming XES parser and the independent raw event count."""

import pandas as pd
import pytest
from conftest import RAW_XML_KEY, xes_event

from meridian.ingestion import schema
from meridian.ingestion.xes import count_raw_events, parse_xes

TRACES = [
    {
        "case_id": "c1",
        "events": [
            xes_event("Submit", "complete", "2016-01-01T09:00:00.000Z", "User_1"),
            xes_event("Review", "start", "2016-01-01T10:00:00.000Z", "User_2"),
            xes_event("Review", "complete", "2016-01-01T11:00:00.000Z", "User_2"),
        ],
    },
    {
        "case_id": "c2",
        "events": [xes_event("Submit", "complete", "2016-01-02T09:00:00.000Z", "User_1")],
    },
]


def test_parse_emits_one_row_per_event_in_file_order(write_xes) -> None:
    """Row order and source positions are what event ordering, and so the DFG, rely on."""
    frame = parse_xes(write_xes(TRACES))

    assert tuple(frame.columns) == schema.RAW_COLUMNS
    columns = [schema.CASE_ID, schema.EVENT_INDEX, schema.ACTIVITY, schema.LIFECYCLE]
    assert frame[columns].to_numpy().tolist() == [
        ["c1", 0, "Submit", "complete"],
        ["c1", 1, "Review", "start"],
        ["c1", 2, "Review", "complete"],
        ["c2", 0, "Submit", "complete"],
    ]
    assert frame.loc[2, schema.RESOURCE] == "User_2"
    assert frame.loc[3, schema.TIMESTAMP] == "2016-01-02T09:00:00.000Z"


@pytest.mark.parametrize("gz", [False, True])
def test_parsed_row_count_matches_independent_byte_count(write_xes, gz: bool) -> None:
    """The before/after row-count check (02-TECH-STACK): parser output equals the file's count."""
    path = write_xes(TRACES, gz=gz)

    assert count_raw_events(path) == len(parse_xes(path)) == 4


@pytest.mark.parametrize("chunk_bytes", [1, 3, 6, 7, 64])
def test_count_finds_tags_split_across_chunk_boundaries(write_xes, chunk_bytes: int) -> None:
    """Tiny chunks force `<event` to straddle boundaries, where a naive count misses or doubles."""
    assert count_raw_events(write_xes(TRACES), chunk_bytes=chunk_bytes) == 4


def test_count_ignores_tags_that_only_start_with_event(tmp_path) -> None:
    """`<events>` or `<eventually>` must not inflate the count the parser is checked against."""
    path = tmp_path / "similar.xes"
    path.write_bytes(
        b"<log><events/><eventually>x</eventually><trace><event></event></trace></log>"
    )

    assert count_raw_events(path) == 1


def test_case_id_declared_after_events_is_still_attached(write_xes) -> None:
    """XES allows trace attributes after the events; the case id must not be lost."""
    traces = [{"case_id": "late", "case_id_last": True, "events": [xes_event("A"), xes_event("B")]}]

    frame = parse_xes(write_xes(traces))

    assert frame[schema.CASE_ID].tolist() == ["late", "late"]


def test_nested_attributes_do_not_override_event_attributes(write_xes) -> None:
    """A nested `concept:name` describes its parent attribute, not the event's activity."""
    nested = '<list key="meta"><string key="concept:name" value="WRONG"/></list>'
    event = xes_event("Submit") | {RAW_XML_KEY: nested}

    frame = parse_xes(write_xes([{"case_id": "c1", "events": [event]}]))

    assert frame.loc[0, schema.ACTIVITY] == "Submit"


def test_default_namespace_is_supported(write_xes) -> None:
    """A namespaced XES file must parse identically instead of silently yielding zero events."""
    path = write_xes(TRACES, namespace="http://www.xes-standard.org/")

    frame = parse_xes(path)

    assert len(frame) == count_raw_events(path) == 4
    assert frame.loc[0, schema.ACTIVITY] == "Submit"


def test_missing_values_parse_as_missing_instead_of_failing(write_xes) -> None:
    """Missing values must reach normalization, where they are counted, rather than crash here."""
    traces = [{"case_id": None, "events": [xes_event("A", timestamp=None, resource=None)]}]

    row = parse_xes(write_xes(traces)).iloc[0]

    assert pd.isna(row[schema.CASE_ID])
    assert pd.isna(row[schema.TIMESTAMP])
    assert pd.isna(row[schema.RESOURCE])
    assert row[schema.ACTIVITY] == "A"
