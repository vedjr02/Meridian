"""Normalization: raw parsed events to the shared normalized event-log schema.

Every event that does not reach the normalized log is counted under exactly one reason, which
makes the requirement "never silently drop data" checkable as an identity:
parsed events = normalized + excluded (malformed, by reason) + filtered (lifecycle projection).
"""

from __future__ import annotations

from collections.abc import Collection, Mapping
from dataclasses import asdict, dataclass

import pandas as pd

from meridian.ingestion import schema

# Malformed-row reasons, in the order they are checked. An event that fails several checks is
# counted once, under the first reason it fails, so the per-reason counts sum to the total.
# `missing_case_id` precedes `duplicate_case_id` because events without a case id would
# otherwise all look like duplicates of each other.
EXCLUSION_REASONS = (
    "missing_case_id",
    "duplicate_case_id",
    "missing_activity",
    "missing_timestamp",
    "unparseable_timestamp",
    "out_of_order",
)

# Events with no lifecycle transition are treated as `complete`: in a log without lifecycle data,
# each event records a finished activity, which is what process-mining tools assume.
DEFAULT_LIFECYCLE = "complete"

NO_TERMINAL_STATE = "no_terminal_state"


@dataclass(frozen=True)
class NormalizationReport:
    """Exact accounting of what normalization kept, excluded and filtered, and why.

    Why `filtered_by_lifecycle` is separate from `excluded`: excluded events are malformed data;
    filtered events are well-formed transitions deliberately left out of the normalized view
    (e.g. `start` when only `complete` is kept). Conflating them would overstate data-quality
    problems by hundreds of thousands of rows on BPI 2017.
    """

    parsed_events: int
    normalized_events: int
    excluded: dict[str, int]
    filtered_by_lifecycle: int
    lifecycle_kept: list[str] | None
    lifecycle_counts: dict[str, int]
    parsed_cases: int
    normalized_cases: int
    events_missing_resource: int
    outcome_counts: dict[str, int]

    @property
    def total_excluded(self) -> int:
        """Number of malformed events excluded, across all reasons."""
        return sum(self.excluded.values())

    @property
    def is_fully_accounted(self) -> bool:
        """Whether every parsed event was normalized, excluded or filtered; none unexplained."""
        accounted = self.normalized_events + self.total_excluded + self.filtered_by_lifecycle
        return self.parsed_events == accounted

    def to_dict(self) -> dict:
        """Return a JSON-serialisable form for the report file and the `ingestion_run` table."""
        return asdict(self) | {
            "total_excluded": self.total_excluded,
            "is_fully_accounted": self.is_fully_accounted,
        }


def _clean_text(series: pd.Series) -> pd.Series:
    """Strip surrounding whitespace and turn empty strings into missing values.

    Why: XES writers emit `value=""` for unknown attributes, and stray whitespace is common in
    labels (BPI 2017 contains "W_Shortened completion " with a trailing space). Without this, a
    blank resource would look present and one activity could appear under two names.
    """
    text = series.astype("string").str.strip()
    return text.mask(text.eq("").fillna(False))


def _counts(series: pd.Series) -> dict[str, int]:
    """Value counts as a plain dict (most frequent first) for JSON reports."""
    return {str(key): int(count) for key, count in series.value_counts().items()}


def normalize_events(
    raw: pd.DataFrame,
    *,
    lifecycle_keep: Collection[str] | None = (DEFAULT_LIFECYCLE,),
    outcome_activities: Mapping[str, str] | None = None,
) -> tuple[pd.DataFrame, NormalizationReport]:
    """Validate, filter and reshape raw events into the normalized event log.

    Args:
        raw: Events shaped like `schema.RAW_COLUMNS`, as produced by `parse_xes`.
        lifecycle_keep: Lifecycle transitions to keep (case-insensitive), or None to keep all.
            Defaults to `complete` only, pending the decision in 08-OPEN-QUESTIONS.md.
        outcome_activities: Maps terminal activities to an outcome label. A case's outcome is the
            label of the last such activity in its normalized events, or NULL if it has none.

    Returns:
        The normalized event log (columns `schema.NORMALIZED_COLUMNS`, sorted by case and source
        position) and a report accounting for every input event.

    Why timestamps are converted to UTC before the order check: comparing local clock times
    would flag false out-of-order events whenever a case spans a daylight-saving change.

    Why out-of-order means "earlier than the latest timestamp seen so far in the case, in file
    order": XES order is the recorder's sequence of events. An event timestamped before something
    already recorded contradicts that sequence, and keeping it would create transitions in the
    directly-follows graph that never happened in that order. Ties are not out of order. The check
    runs only on events that would be kept, since those are the sequence mining will see.
    """
    frame = raw.loc[:, list(schema.RAW_COLUMNS)].copy()
    for column in (
        schema.CASE_ID,
        schema.ACTIVITY,
        schema.LIFECYCLE,
        schema.TIMESTAMP,
        schema.RESOURCE,
    ):
        frame[column] = _clean_text(frame[column])
    frame[schema.LIFECYCLE] = frame[schema.LIFECYCLE].fillna(DEFAULT_LIFECYCLE).str.lower()
    timestamps = pd.to_datetime(
        frame[schema.TIMESTAMP], utc=True, format="ISO8601", errors="coerce"
    )

    reasons = pd.Series(pd.NA, index=frame.index, dtype="string")

    def flag(mask: pd.Series, reason: str) -> None:
        """Record `reason` for rows matching `mask` that have not already failed a check."""
        reasons[mask.to_numpy(dtype=bool) & reasons.isna().to_numpy()] = reason

    missing_case = frame[schema.CASE_ID].isna()
    flag(missing_case, "missing_case_id")
    colliding = frame.duplicated([schema.CASE_ID, schema.EVENT_INDEX], keep=False) & ~missing_case
    flag(frame[schema.CASE_ID].isin(frame.loc[colliding, schema.CASE_ID]), "duplicate_case_id")
    flag(frame[schema.ACTIVITY].isna(), "missing_activity")
    flag(frame[schema.TIMESTAMP].isna(), "missing_timestamp")
    flag(timestamps.isna() & frame[schema.TIMESTAMP].notna(), "unparseable_timestamp")

    if lifecycle_keep is None:
        lifecycle_ok = pd.Series(True, index=frame.index)
    else:
        lifecycle_ok = frame[schema.LIFECYCLE].isin({name.lower() for name in lifecycle_keep})
    well_formed = reasons.isna()
    filtered = well_formed & ~lifecycle_ok
    candidates = well_formed & lifecycle_ok

    ordered = pd.DataFrame(
        {
            schema.CASE_ID: frame.loc[candidates, schema.CASE_ID],
            schema.EVENT_INDEX: frame.loc[candidates, schema.EVENT_INDEX],
            schema.TIMESTAMP: timestamps[candidates],
        }
    ).sort_values([schema.CASE_ID, schema.EVENT_INDEX], kind="stable")
    running_max = ordered.groupby(schema.CASE_ID, sort=False)[schema.TIMESTAMP].cummax()
    previous_max = running_max.groupby(ordered[schema.CASE_ID], sort=False).shift()
    out_of_order = ordered.index[(ordered[schema.TIMESTAMP] < previous_max).to_numpy()]
    flag(pd.Series(frame.index.isin(out_of_order), index=frame.index), "out_of_order")

    kept = candidates & reasons.isna()
    event_log = pd.DataFrame(
        {
            schema.CASE_ID: frame.loc[kept, schema.CASE_ID],
            schema.EVENT_INDEX: frame.loc[kept, schema.EVENT_INDEX].astype("int64"),
            schema.ACTIVITY: frame.loc[kept, schema.ACTIVITY],
            schema.TIMESTAMP: timestamps[kept],
            schema.RESOURCE: frame.loc[kept, schema.RESOURCE],
        }
    ).sort_values([schema.CASE_ID, schema.EVENT_INDEX], kind="stable")
    # BPI 2017 records no per-event cost, so the optional column exists but stays empty rather
    # than being filled with an invented figure.
    event_log[schema.COST] = float("nan")
    event_log[schema.OUTCOME] = _case_outcomes(event_log, outcome_activities or {})
    event_log = event_log.loc[:, list(schema.NORMALIZED_COLUMNS)].reset_index(drop=True)

    per_case_outcome = event_log.drop_duplicates(schema.CASE_ID)[schema.OUTCOME]
    report = NormalizationReport(
        parsed_events=len(frame),
        normalized_events=len(event_log),
        excluded={reason: int(reasons.eq(reason).sum()) for reason in EXCLUSION_REASONS},
        filtered_by_lifecycle=int(filtered.sum()),
        lifecycle_kept=None
        if lifecycle_keep is None
        else sorted(n.lower() for n in lifecycle_keep),
        lifecycle_counts=_counts(frame[schema.LIFECYCLE]),
        parsed_cases=int(frame[schema.CASE_ID].nunique()),
        normalized_cases=int(event_log[schema.CASE_ID].nunique()),
        events_missing_resource=int(event_log[schema.RESOURCE].isna().sum()),
        outcome_counts=_counts(per_case_outcome.fillna(NO_TERMINAL_STATE)),
    )
    return event_log, report


def _case_outcomes(event_log: pd.DataFrame, outcome_activities: Mapping[str, str]) -> pd.Series:
    """Label each event with its case's outcome: the label of the case's last terminal activity.

    Why the last one rather than the first: an outcome describes where a case ended, and a later
    terminal state supersedes an earlier one in logs where decisions get revised. Checked on BPI
    2017: no case reaches two different terminal states; one case records A_Denied twice, which is
    why the log has 3,753 A_Denied events but 3,752 denied cases.
    """
    if not outcome_activities:
        return pd.Series(pd.NA, index=event_log.index, dtype="string")
    terminal = event_log[event_log[schema.ACTIVITY].isin(list(outcome_activities))]
    last_terminal = terminal.groupby(schema.CASE_ID, sort=False)[schema.ACTIVITY].last()
    case_outcome = last_terminal.map(dict(outcome_activities))
    return event_log[schema.CASE_ID].map(case_outcome).astype("string")
