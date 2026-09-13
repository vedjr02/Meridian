"""Tests for the written diagnostic report against a log whose every figure is derived by hand.

Log: the four rework cases from `test_rework.py` (25 case-hours of cycle time), checked against the
documented reference A, B, D.

Replay (p0 -A-> p1 -B-> p2 -D-> p3): r3 fits exactly; r2 repeats B (m 1, r 1, fitness 0.8); r1 has
two unknown C and a repeated B (m 3, r 3, c = p = 7); r4 has unknown C and E and a repeated B
(m 3, r 3, c = p = 8). Pooled: m = r = 7 over c = p = 24, so log fitness is 17/24 = 0.708, and
3 of 4 cases (75.0%) deviate.

Bottlenecks (hours): D -> E is one 6 h wait, the largest total, 24.0% of 25 h.
Rework: 15.5 case-hours, 62.0% of cycle time, 3 cases; per affected case median 5 h, p90 9 h.
"""

import pytest
from test_rework import CASES, HOUR, hours_log

from meridian.conformance.bottlenecks import analyze_bottlenecks
from meridian.conformance.pipeline import run_conformance
from meridian.conformance.reference import ReferenceStrategy
from meridian.conformance.report import DiagnosticInputs, render_diagnostic_report
from meridian.conformance.rework import analyze_rework
from meridian.ingestion.lifecycle import LifecyclePolicy

LOG = hours_log(CASES)


@pytest.fixture
def inputs(discovery_settings) -> DiagnosticInputs:
    """Every analysis run on the hand-derived log; conformance against the reference A, B, D."""
    conformance = run_conformance(
        discovery_settings,
        ReferenceStrategy.DOCUMENTED,
        documented_activities=["A", "B", "D"],
        event_log=LOG,
    )
    return DiagnosticInputs(
        dataset_name="Synthetic",
        lifecycle=LifecyclePolicy.START_ELSE_COMPLETE,
        conformance=conformance.summary,
        bottlenecks=analyze_bottlenecks(LOG, min_occurrences=1, slow_threshold_seconds=2 * HOUR),
        rework=analyze_rework(LOG),
    )


def test_question_one_share_deviating_with_fitness_and_reference(inputs) -> None:
    """Deviation share, log fitness and the reference used, all in the answer."""
    text = render_diagnostic_report(inputs)

    assert "**1. What share of cases deviate from the intended path?** 75.0% (3 of 4 cases)" in text
    assert "Log fitness is 0.708" in text
    assert "Reference: Documented intended process of 3 activities." in text


def test_question_two_costliest_transition(inputs) -> None:
    """D -> E: 6 case-hours, 24.0% of elapsed time, one occurrence, uniformly slow."""
    text = render_diagnostic_report(inputs)

    assert (
        "**2. Which single transition costs the most aggregate time?** `D` → `E`: 6.0 case-hours, "
        "24.0% of all elapsed time between events, over 1 occurrence." in text
    )
    assert "bottleneck classification: uniformly slow." in text


def test_question_three_rework_cost(inputs) -> None:
    """15.5 case-hours, 62.0% of cycle time, 3 cases; median 5 h and p90 9 h per affected case."""
    text = render_diagnostic_report(inputs)

    assert (
        "**3. How much total cycle time does rework add?** 15.5 case-hours, 62.0% of all recorded "
        "cycle time, sit inside rework loops, across 3 cases (75.0% of cases)." in text
    )
    assert "median of 5.0 h and a p90 of 9.0 h" in text


def test_every_answer_cites_numbers(inputs) -> None:
    """Module B req. 5: no claim without a number. Each answer paragraph must contain digits."""
    text = render_diagnostic_report(inputs)

    answers = [line for line in text.splitlines() if line.startswith(("**1.", "**2.", "**3."))]
    assert len(answers) == 3
    assert all(any(character.isdigit() for character in answer) for answer in answers)


def test_evidence_sections_and_caveats(inputs) -> None:
    """Reference path, fitness table, bottleneck and rework tables, and the attribution caveats."""
    text = render_diagnostic_report(inputs)

    assert "Reference path: `A` → `B` → `D`" in text
    assert "| Cases following the reference exactly | 1 |" in text
    assert "| no terminal state |" in text
    assert "**Uniformly slow** (4 transitions)" in text
    assert "| `B` | 3 | 3 |" in text  # B repeated in 3 cases, 3 repetitions
    assert "Lifecycle rule: start where recorded, otherwise complete." in text
    assert "not a guaranteed saving" in text


def test_log_without_rework_gets_a_plain_answer(discovery_settings) -> None:
    """No repeated activities: say so, rather than print medians of nothing."""
    log = hours_log({"r3": CASES["r3"]})
    conformance = run_conformance(
        discovery_settings,
        ReferenceStrategy.MOST_FREQUENT_VARIANT,
        event_log=log,
    )

    text = render_diagnostic_report(
        DiagnosticInputs(
            dataset_name="Synthetic",
            lifecycle=LifecyclePolicy.ALL,
            conformance=conformance.summary,
            bottlenecks=analyze_bottlenecks(log, min_occurrences=1),
            rework=analyze_rework(log),
        )
    )

    assert "No case repeats an activity, so rework adds no cycle time." in text
    assert "Lifecycle rule: every transition." in text


def test_report_is_deterministic(inputs) -> None:
    """Same inputs, same document: no LLM and no randomness."""
    assert render_diagnostic_report(inputs) == render_diagnostic_report(inputs)
