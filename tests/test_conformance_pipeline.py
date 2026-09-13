"""Tests for the conformance run and command.

Synthetic log (conftest `discovery_settings`): c1 and c2 follow Submit, Review, Approve (approved);
c3 follows Submit, Reject (rejected). Against reference Submit, Review, Approve, c3 replays as:
Submit fires; Reject is unknown (+1 missing, +1 remaining); the final place is empty (+1 missing);
Submit's token is left in p1 (+1 remaining). So c3 has m = 2, r = 2, c = 3, p = 3: fitness 1/3.
Pooled over the log: m = 2, r = 2, c = 4 + 4 + 3 = 11, p = 11, so log fitness = 9/11.
"""

import dataclasses
import json
import shutil

import pytest

from meridian.config import get_settings
from meridian.conformance import pipeline
from meridian.conformance.pipeline import run_conformance
from meridian.conformance.reference import ReferenceStrategy
from meridian.discovery.pipeline import run_discovery

REAL_SETTINGS = get_settings()


@pytest.fixture
def settings(discovery_settings):
    """Settings whose processed directory holds the synthetic normalized log."""
    run_discovery(discovery_settings, load_database=False)
    return discovery_settings


def test_most_frequent_reference_scores_every_case(settings) -> None:
    """Two exact fits and one case at fitness 1/3; aggregates follow from pooled token counts."""
    result = run_conformance(settings, ReferenceStrategy.MOST_FREQUENT_VARIANT)

    assert result.reference.activities == ("Submit", "Review", "Approve")
    fitness = dict(zip(result.replay.cases["case_id"], result.replay.cases["fitness"], strict=True))
    assert fitness == pytest.approx({"c1": 1.0, "c2": 1.0, "c3": 1 / 3})
    assert result.summary["fitting_cases"] == 2
    assert result.summary["deviating_share"] == pytest.approx(1 / 3)
    assert result.summary["log_fitness"] == pytest.approx(9 / 11)
    assert result.summary["mean_case_fitness_by_outcome"] == pytest.approx(
        {"approved": 1.0, "rejected": 1 / 3}
    )


def test_outputs_record_what_the_numbers_were_measured_against(settings) -> None:
    """The summary must carry the reference, how it was chosen and the data's lifecycle filter."""
    run_conformance(
        settings, ReferenceStrategy.MOST_FREQUENT_VARIANT_FOR_OUTCOME, outcome="rejected"
    )

    summary = json.loads(settings.conformance_summary_json.read_text())
    assert summary["reference"]["strategy"] == "most_frequent_variant_for_outcome"
    assert summary["reference"]["outcome"] == "rejected"
    assert summary["reference"]["activities"] == ["Submit", "Reject"]
    assert "outcome 'rejected'" in summary["reference"]["description"]
    assert summary["lifecycle_kept"] == "complete"
    assert summary["fitness_formula"].startswith("0.5 * (1 - missing / consumed)")
    assert settings.conformance_cases_csv.read_text().count("\n") == 4  # header + 3 cases


def test_command_requires_an_explicit_reference(settings, monkeypatch, capsys) -> None:
    """Omitting --reference is a usage error: the choice is never made silently."""
    monkeypatch.setattr(pipeline, "get_settings", lambda: settings)

    with pytest.raises(SystemExit) as exit_info:
        pipeline.main([])

    assert exit_info.value.code == 2
    assert "--reference" in capsys.readouterr().err


def test_command_runs_and_reports_selection_errors(settings, monkeypatch, capsys) -> None:
    """A valid run prints the reference description; an outcome strategy without --outcome fails."""
    monkeypatch.setattr(pipeline, "get_settings", lambda: settings)

    assert pipeline.main(["--reference", "most_frequent_variant"]) == 0
    assert "Cases fitting exactly: 2 of 3" in capsys.readouterr().out

    assert pipeline.main(["--reference", "most_frequent_variant_for_outcome"]) == 1
    assert "needs an outcome" in capsys.readouterr().err


def test_command_explains_missing_event_log(tmp_path, monkeypatch, capsys) -> None:
    """Without ingestion output the command says what to run."""
    monkeypatch.setenv("MERIDIAN_DATA_DIR", str(tmp_path))

    assert pipeline.main(["--reference", "most_frequent_variant"]) == 1
    assert "python -m meridian.discovery" in capsys.readouterr().err


@pytest.mark.integration
@pytest.mark.skipif(
    not REAL_SETTINGS.event_log_csv.exists(), reason="run `python -m meridian.discovery` first"
)
@pytest.mark.parametrize(
    ("strategy", "outcome"),
    [
        (ReferenceStrategy.MOST_FREQUENT_VARIANT, None),
        (ReferenceStrategy.MOST_FREQUENT_VARIANT_FOR_OUTCOME, "pending"),
    ],
)
def test_real_log_conformance_invariants(tmp_path, strategy, outcome) -> None:
    """On BPI 2017, for both candidate references (neither is chosen here), results are consistent.

    Every case is replayed. A case fits exactly only if it follows the reference sequence, so
    fitting cases are at least the reference's supporting cases (equal for the overall most
    frequent variant), and aggregates stay within [0, 1]. Exact values depend on the open
    lifecycle and reference questions, so they are not pinned.
    """
    (tmp_path / "processed").mkdir()
    shutil.copy(REAL_SETTINGS.event_log_csv, tmp_path / "processed" / "event_log.csv")
    settings = dataclasses.replace(REAL_SETTINGS, data_dir=tmp_path)

    result = run_conformance(settings, strategy, outcome=outcome)

    assert result.replay.case_count == 31_509
    assert result.replay.fitting_cases >= result.reference.supporting_cases
    if strategy is ReferenceStrategy.MOST_FREQUENT_VARIANT:
        assert result.replay.fitting_cases == result.reference.supporting_cases
    assert 0.0 <= result.summary["log_fitness"] <= 1.0
    assert 0.0 <= result.summary["deviating_share"] <= 1.0
