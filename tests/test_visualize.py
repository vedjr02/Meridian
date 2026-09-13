"""Tests for the Mermaid rendering of the directly-follows graph."""

import re

import pytest
from test_dfg import LOG as DAY3_LOG
from test_dfg import make_log

from meridian.discovery.dfg import build_dfg
from meridian.discovery.visualize import dfg_to_mermaid

DFG = build_dfg(DAY3_LOG)  # 9 edges, 15 transitions; A->B is the most frequent (4)


def test_diagram_contains_nodes_edges_and_frequency_labels() -> None:
    """Every shown activity is a labelled node with its event count; edges carry frequencies."""
    diagram = dfg_to_mermaid(DFG)

    lines = diagram.text.splitlines()
    assert lines[0] == "flowchart LR"
    assert '["A<br/>6"]' in diagram.text  # A has 6 events
    assert sum(1 for line in lines if "-->" in line) == 9
    assert re.search(r'-->\|"4"\|', diagram.text)


def test_edge_limit_and_coverage_caption() -> None:
    """Top 3 edges carry 4 + 2 + 2 = 8 of 15 transitions; the caption must say so."""
    diagram = dfg_to_mermaid(DFG, max_edges=3)

    assert diagram.edges_shown == 3
    assert diagram.edges_total == 9
    assert diagram.transition_share == pytest.approx(8 / 15)
    assert "3 most frequent of 9" in diagram.caption
    assert "53.3%" in diagram.caption


def test_line_width_grows_with_frequency() -> None:
    """Width encodes frequency (03-UIUX-RULES Module A): the most frequent edge is widest."""
    widths = [
        float(width) for width in re.findall(r"stroke-width:([\d.]+)px", dfg_to_mermaid(DFG).text)
    ]

    assert widths[0] == 8.0
    assert widths == sorted(widths, reverse=True)
    assert min(widths) >= 1.0


def test_labels_are_escaped() -> None:
    """Quotes or angle brackets in activity names must not break the diagram."""
    log = make_log({"c1": [('Say "hi"', "09:00"), ("a<b>", "09:01")]})

    text = dfg_to_mermaid(build_dfg(log)).text

    assert "#quot;hi#quot;" in text
    assert "a#lt;b#gt;" in text


def test_rendering_is_deterministic_and_rejects_bad_limit() -> None:
    """Same graph, same text; a limit below one edge is a caller error."""
    assert dfg_to_mermaid(DFG).text == dfg_to_mermaid(build_dfg(DAY3_LOG)).text
    with pytest.raises(ValueError):
        dfg_to_mermaid(DFG, max_edges=0)
