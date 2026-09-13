"""Tests for normalization: schema shape, exclusion accounting, ordering and outcomes."""

import pandas as pd

from meridian.ingestion import schema
from meridian.ingestion.lifecycle import LifecyclePolicy
from meridian.ingestion.normalize import EXCLUSION_REASONS, normalize_events


def raw(rows: list[tuple]) -> pd.DataFrame:
    """Build a raw events frame from (case, index, activity, lifecycle, timestamp, resource)."""
    return pd.DataFrame(rows, columns=list(schema.RAW_COLUMNS))


CLEAN = [
    ("c1", 0, "Submit", "complete", "2016-01-01T09:00:00.000Z", "User_1"),
    ("c1", 1, "Review", "start", "2016-01-01T10:00:00.000Z", "User_2"),
    ("c1", 2, "Review", "complete", "2016-01-01T11:00:00.000Z", "User_2"),
    ("c1", 3, "Approve", "complete", "2016-01-01T12:00:00.000Z", "User_3"),
    ("c2", 0, "Submit", "complete", "2016-01-02T09:00:00.000Z", "User_1"),
    ("c2", 1, "Reject", "complete", "2016-01-02T10:00:00.000Z", "User_3"),
]

MESSY = [
    ("c1", 0, "Submit", "complete", "2016-01-01T09:00:00.000Z", "User_1"),  # kept
    ("c1", 1, "Review", "complete", None, "User_2"),  # missing_timestamp
    ("c1", 2, "Review", "complete", "yesterday", "User_2"),  # unparseable_timestamp
    ("c1", 3, "Check", "complete", "2016-01-01T12:00:00.000Z", "User_2"),  # kept
    ("c1", 4, "Check", "complete", "2016-01-01T11:00:00.000Z", "User_2"),  # out_of_order
    ("c1", 5, "  ", "complete", "2016-01-01T13:00:00.000Z", "User_2"),  # missing_activity
    ("c1", 6, "Approve", "complete", "2016-01-01T14:00:00.000Z", ""),  # kept, no resource
    ("c1", 7, None, "complete", None, "User_2"),  # missing_activity (first check it fails)
    (None, 0, "Submit", "complete", "2016-01-03T09:00:00.000Z", "User_1"),  # missing_case_id
    ("dup", 0, "Submit", "complete", "2016-01-04T09:00:00.000Z", "User_1"),  # duplicate_case_id
    ("dup", 0, "Submit", "complete", "2016-01-05T09:00:00.000Z", "User_1"),  # duplicate_case_id
    ("dup", 1, "Approve", "complete", "2016-01-05T10:00:00.000Z", "User_3"),  # duplicate_case_id
]


def test_output_columns_are_exactly_the_shared_schema() -> None:
    """Downstream modules read these columns by name; any drift must fail loudly here."""
    event_log, _ = normalize_events(raw(CLEAN))

    assert tuple(event_log.columns) == schema.NORMALIZED_COLUMNS
    assert event_log[schema.COST].isna().all()


def test_complete_only_projection_is_counted_as_filtered_not_excluded() -> None:
    """Dropping `start` transitions is a deliberate view, not bad data; the report must say so."""
    event_log, report = normalize_events(raw(CLEAN), lifecycle=LifecyclePolicy.COMPLETE)

    assert report.normalized_events == len(event_log) == 5
    assert report.filtered_by_lifecycle == 1
    assert report.total_excluded == 0
    assert report.lifecycle_counts == {"complete": 5, "start": 1}
    assert report.is_fully_accounted


def test_keeping_all_lifecycles_filters_nothing() -> None:
    """The ALL policy keeps every transition (the logged future-work option)."""
    event_log, report = normalize_events(raw(CLEAN), lifecycle=LifecyclePolicy.ALL)

    assert len(event_log) == 6
    assert report.filtered_by_lifecycle == 0
    assert report.lifecycle_policy == "all"


def test_start_else_complete_represents_started_activities_by_their_start() -> None:
    """Default policy: Review records a start, so its start is kept and its complete filtered.

    Submit, Approve and Reject never record a start, so their complete events are kept. Result:
    5 events (Review at 10:00, when work began, not 11:00), 1 filtered, and the report names Review.
    """
    event_log, report = normalize_events(raw(CLEAN))

    review = event_log[event_log[schema.ACTIVITY] == "Review"]
    assert review[schema.EVENT_INDEX].tolist() == [1]
    assert review[schema.TIMESTAMP].tolist() == [pd.Timestamp("2016-01-01T10:00:00Z")]
    assert report.normalized_events == 5
    assert report.filtered_by_lifecycle == 1
    assert report.lifecycle_policy == "start_else_complete"
    assert report.activities_represented_by_start == ["Review"]
    assert report.is_fully_accounted


def test_started_work_item_without_a_complete_is_still_counted() -> None:
    """The reason for the policy: aborted work items (start, then ate_abort) must not vanish.

    Under complete-only the aborted Call below disappears entirely; under the default it is kept.
    """
    rows = [
        ("c1", 0, "Call", "schedule", "2016-01-01T08:00:00Z", "u"),
        ("c1", 1, "Call", "start", "2016-01-01T09:00:00Z", "u"),
        ("c1", 2, "Call", "ate_abort", "2016-01-01T09:30:00Z", "u"),
        ("c2", 0, "Call", "start", "2016-01-02T09:00:00Z", "u"),
        ("c2", 1, "Call", "complete", "2016-01-02T09:20:00Z", "u"),
    ]

    started, _ = normalize_events(raw(rows))
    completed, _ = normalize_events(raw(rows), lifecycle=LifecyclePolicy.COMPLETE)

    assert len(started) == 2
    assert len(completed) == 1


def test_malformed_events_are_excluded_once_each_with_a_reason() -> None:
    """The requirement: never drop data without a count of how much was dropped and why."""
    event_log, report = normalize_events(raw(MESSY))

    assert report.excluded == {
        "missing_case_id": 1,
        "duplicate_case_id": 3,
        "missing_activity": 2,
        "missing_timestamp": 1,
        "unparseable_timestamp": 1,
        "out_of_order": 1,
    }
    assert list(report.excluded) == list(EXCLUSION_REASONS)
    kept = event_log[[schema.CASE_ID, schema.EVENT_INDEX]].to_numpy().tolist()
    assert kept == [["c1", 0], ["c1", 3], ["c1", 6]]
    assert report.parsed_events == 12
    assert report.is_fully_accounted


def test_missing_resource_is_kept_as_null_and_counted() -> None:
    """A missing performer does not break process mining, but Module E needs to know about it."""
    event_log, report = normalize_events(raw(MESSY))

    assert event_log[schema.RESOURCE].isna().tolist() == [False, False, True]
    assert report.events_missing_resource == 1


def test_equal_timestamps_are_not_out_of_order() -> None:
    """Ties are common for system-generated events and do not contradict the file's order."""
    rows = [
        ("c1", 0, "A", "complete", "2016-01-01T09:00:00.000Z", "u"),
        ("c1", 1, "B", "complete", "2016-01-01T09:00:00.000Z", "u"),
    ]

    event_log, report = normalize_events(raw(rows))

    assert len(event_log) == 2
    assert report.excluded["out_of_order"] == 0


def test_order_is_checked_in_utc_across_a_daylight_saving_change() -> None:
    """Dutch clocks went back an hour on 30 Oct 2016; in UTC these two events are in order."""
    rows = [
        ("c1", 0, "A", "complete", "2016-10-30T02:30:00.000+02:00", "u"),  # 00:30 UTC
        ("c1", 1, "B", "complete", "2016-10-30T02:10:00.000+01:00", "u"),  # 01:10 UTC
    ]

    event_log, report = normalize_events(raw(rows))

    assert report.excluded["out_of_order"] == 0
    assert event_log[schema.TIMESTAMP].tolist() == [
        pd.Timestamp("2016-10-30T00:30:00Z"),
        pd.Timestamp("2016-10-30T01:10:00Z"),
    ]


def test_missing_lifecycle_counts_as_complete_and_matching_ignores_case() -> None:
    """Logs without lifecycle data, or with upper-case values, must not be filtered to nothing."""
    rows = [
        ("c1", 0, "A", None, "2016-01-01T09:00:00.000Z", "u"),
        ("c1", 1, "B", "COMPLETE", "2016-01-01T10:00:00.000Z", "u"),
    ]

    event_log, report = normalize_events(raw(rows))

    assert len(event_log) == 2
    assert report.filtered_by_lifecycle == 0


def test_labels_are_whitespace_trimmed() -> None:
    """BPI 2017's "W_Shortened completion " must not become a second, distinct activity."""
    rows = [("c1", 0, "W_Shortened completion ", "complete", "2016-01-01T09:00:00Z", " User_1 ")]

    event_log, _ = normalize_events(raw(rows))

    assert event_log.loc[0, schema.ACTIVITY] == "W_Shortened completion"
    assert event_log.loc[0, schema.RESOURCE] == "User_1"


def test_outcome_is_the_last_terminal_activity_of_each_case() -> None:
    """A case's outcome is how it ended, so a later terminal state overrides an earlier one."""
    rows = CLEAN + [
        ("c3", 0, "Reject", "complete", "2016-01-03T09:00:00.000Z", "User_3"),
        ("c3", 1, "Approve", "complete", "2016-01-03T10:00:00.000Z", "User_3"),
        ("c4", 0, "Submit", "complete", "2016-01-04T09:00:00.000Z", "User_1"),
    ]
    outcomes = {"Approve": "approved", "Reject": "rejected"}

    event_log, report = normalize_events(raw(rows), outcome_activities=outcomes)

    by_case = event_log.drop_duplicates(schema.CASE_ID).set_index(schema.CASE_ID)[schema.OUTCOME]
    assert by_case["c1"] == "approved"
    assert by_case["c2"] == "rejected"
    assert by_case["c3"] == "approved"
    assert pd.isna(by_case["c4"])
    assert report.outcome_counts == {"approved": 2, "rejected": 1, "no_terminal_state": 1}


def test_raw_input_is_not_modified() -> None:
    """The pipeline also writes the raw table to disk, so normalization must not mutate it."""
    frame = raw(MESSY)
    before = frame.copy()

    normalize_events(frame)

    pd.testing.assert_frame_equal(frame, before)
