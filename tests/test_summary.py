"""Tests for the written discovery summary, against a log whose every figure is hand-computed.

Log: 6 cases `S A B E` taking 2 days (approved), 3 cases `S A E` taking 1 day (rejected), and
1 case `S B E` taking 10 days with no outcome. Sorted cycle times in days are
[1, 1, 1, 2, 2, 2, 2, 2, 2, 10]: p50 2.0, p90 2 + 0.1 x 8 = 2.8, p99 2 + 0.91 x 8 = 9.3, mean 2.5.
"""

import pandas as pd
from test_heuristic_net import LOG as LOOP_LOG

from meridian.discovery.cycle_time import case_statistics
from meridian.discovery.dfg import build_dfg
from meridian.discovery.heuristic_miner import mine_heuristic_net
from meridian.discovery.summary import DiscoveryInputs, format_duration, render_summary
from meridian.discovery.variants import analyze_variants
from meridian.discovery.visualize import dfg_to_mermaid
from meridian.ingestion import schema

SPEC = [("S A B E", 6, 2, "approved"), ("S A E", 3, 1, "rejected"), ("S B E", 1, 10, None)]


def build_log(spec: list[tuple[str, int, float, str | None]]) -> pd.DataFrame:
    """Build a log from (activities, case count, duration in days, outcome) rows."""
    rows, number = [], 0
    for activities, count, days, outcome in spec:
        names = activities.split()
        step = pd.Timedelta(days=days) / (len(names) - 1)
        for _ in range(count):
            number += 1
            start = pd.Timestamp("2016-01-01T00:00:00Z") + pd.Timedelta(days=number)
            rows += [
                (f"case{number:02d}", i, name, start + step * i, "u", None, outcome)
                for i, name in enumerate(names)
            ]
    return pd.DataFrame(rows, columns=list(schema.NORMALIZED_COLUMNS))


def make_inputs(log: pd.DataFrame, lifecycle_kept: str = "complete") -> DiscoveryInputs:
    """Run every discovery step on `log` and bundle the results for the renderer."""
    dfg = build_dfg(log)
    variants = analyze_variants(log)
    return DiscoveryInputs(
        dataset_name="Synthetic",
        dfg=dfg,
        net=mine_heuristic_net(log),
        variants=variants,
        case_stats=case_statistics(log, variants),
        diagram=dfg_to_mermaid(dfg),
        lifecycle_kept=lifecycle_kept,
    )


LOG = build_log(SPEC)
TEXT = render_summary(make_inputs(LOG))


def test_duration_formatting_switches_to_hours_below_a_day() -> None:
    """Readers see "2.0 days" for long spans and "3.0 h" for short ones."""
    assert format_duration(2 * 86_400) == "2.0 days"
    assert format_duration(3 * 3_600) == "3.0 h"


def test_header_and_headline_numbers() -> None:
    """Scope line and the 80% coverage headline: 8 of 10 cases need variants of 6 and 3 cases."""
    assert "Computed from 36 events in 10 cases across 4 activities" in TEXT
    assert "(lifecycle transitions kept: complete)" in TEXT
    assert (
        "**Covering 80% of cases takes 2 of 3 distinct variants (66.7% of all variants).**" in TEXT
    )
    assert "The most common variant accounts for 60.0% of cases" in TEXT
    assert "1 variant was followed by a single case (33.3% of variants)" in TEXT


def test_variant_table_shows_outcome_mix_per_variant() -> None:
    """Each top variant carries its outcome mix, including cases with no outcome."""
    assert "| 1 | 6 | 60.0% | 60.0% | 4 | approved 100% |" in TEXT
    assert "| 2 | 3 | 30.0% | 90.0% | 3 | rejected 100% |" in TEXT
    assert "| 3 | 1 | 10.0% | 100.0% | 3 | no terminal state 100% |" in TEXT
    assert "Most common variant: `S > A > B > E`" in TEXT
    assert "- rejected: rank 2, 3 cases (100.0% of 3 rejected cases)" in TEXT


def test_cycle_time_is_reported_as_a_distribution() -> None:
    """Acceptance (d): p50/p90/p99 per group, and the mean compared against the median."""
    assert "| All cases | 10 | 2.0 days | 2.8 days | 9.3 days | 2.5 days | 10.0 days |" in TEXT
    assert (
        "| Most common variant | 6 | 2.0 days | 2.0 days | 2.0 days | 2.0 days | 2.0 days |" in TEXT
    )
    assert "| All other variants | 4 |" in TEXT
    assert "Half of all cases finish within 2.0 days" in TEXT
    assert "The mean (2.5 days) is 25% above the median" in TEXT


def test_process_map_and_model_sections() -> None:
    """The DFG diagram is embedded; the model states its edge mix and that nothing is orphaned."""
    assert "```mermaid\nflowchart LR" in TEXT
    assert "Dependency threshold 0.9: 3 edges (1 causal, 0 length-one loops, " in TEXT
    assert "2 best connections)" in TEXT
    assert "Orphan activities: none." in TEXT


def test_caveats_cover_lifecycle_happy_path_and_open_cases() -> None:
    """A reader must see what limits every number before quoting it."""
    assert "Only `complete` lifecycle transitions are in this log." in TEXT
    assert "Its cases end: approved 100%." in TEXT
    assert "1 case has no terminal state (10.0%)" in TEXT
    assert "linear interpolation" in TEXT


def test_lifecycle_caveat_is_omitted_when_all_transitions_are_kept() -> None:
    """The caveat explains a filter; with no filter there is nothing to explain."""
    text = render_summary(make_inputs(LOG, lifecycle_kept="all"))

    assert "lifecycle transitions are in this log" not in text


def test_loops_are_listed_as_rework_leads() -> None:
    """Loop log from the model tests: A and B loop (40 forward, 10 back); C repeats 10 times."""
    text = render_summary(make_inputs(LOOP_LOG))

    assert "- `A` ⇄ `B`: 40 forward, 10 back (length-two loop, measure 0.952)" in text
    assert "- `C` repeats immediately: 10 times (length-one loop, measure 0.909)" in text


def test_summary_is_deterministic() -> None:
    """Identical inputs must yield an identical document (no LLM, no randomness)."""
    assert render_summary(make_inputs(LOG)) == TEXT
