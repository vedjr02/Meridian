"""Text-based process-map rendering: the directly-follows graph as a Mermaid flowchart.

Why Mermaid: it renders directly on GitHub, in the README and in most editors, needs no new
dependency, and is already the accepted diagram format for Module C. The interactive process map
is the frontend's job; this gives the command line a real visualization (Module A acceptance a).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from meridian.discovery.dfg import FREQUENCY, SOURCE, TARGET, DirectlyFollowsGraph

DEFAULT_MAX_EDGES = 40

_MIN_WIDTH_PX = 1.0
_MAX_WIDTH_PX = 8.0


@dataclass(frozen=True)
class MermaidDiagram:
    """A rendered diagram plus how much of the graph it shows.

    Why the coverage numbers travel with the text: a filtered process map that does not say what
    it omits invites readers to assume they are seeing the whole process.
    """

    text: str
    edges_shown: int
    edges_total: int
    transition_share: float

    @property
    def caption(self) -> str:
        """One-line description of what the diagram includes and how to read it."""
        return (
            f"Showing the {self.edges_shown} most frequent of {self.edges_total} directly-follows "
            f"edges, covering {self.transition_share:.1%} of all transitions. "
            "Line width and labels encode frequency."
        )


def _escape_label(text: str) -> str:
    """Escape characters that would end or break a quoted Mermaid label."""
    return text.replace('"', "#quot;").replace("<", "#lt;").replace(">", "#gt;")


def _stroke_width(frequency: int, max_frequency: int) -> float:
    """Map an edge frequency to a line width between 1 and 8 px.

    Why square-root scaling: frequencies on real logs span four orders of magnitude; linear widths
    would render all but the top few edges as hairlines, while square-root scaling keeps mid-sized
    flows visible and still preserves order.
    """
    if max_frequency <= 0:
        return _MIN_WIDTH_PX
    scaled = math.sqrt(frequency / max_frequency)
    return round(_MIN_WIDTH_PX + (_MAX_WIDTH_PX - _MIN_WIDTH_PX) * scaled, 1)


def dfg_to_mermaid(dfg: DirectlyFollowsGraph, max_edges: int = DEFAULT_MAX_EDGES) -> MermaidDiagram:
    """Render the most frequent DFG edges as a left-to-right Mermaid flowchart.

    Why only the top edges: BPI 2017 has 159 edges, and a diagram with all of them is unreadable.
    The edges table is already sorted by frequency with a fixed tie order, so the selection, node
    ids and line order are identical across runs.
    """
    if max_edges < 1:
        raise ValueError(f"max_edges must be at least 1, got {max_edges}")
    shown = dfg.edges.head(max_edges)
    activities = sorted(set(shown[SOURCE]) | set(shown[TARGET]))
    node_id = {activity: f"n{index}" for index, activity in enumerate(activities)}
    max_frequency = int(shown[FREQUENCY].max()) if len(shown) else 0

    lines = ["flowchart LR"]
    lines += [
        f'    {node_id[a]}["{_escape_label(a)}<br/>{dfg.activity_counts[a]:,}"]' for a in activities
    ]
    edges = list(shown[[SOURCE, TARGET, FREQUENCY]].itertuples(index=False, name=None))
    lines += [
        f'    {node_id[source]} -->|"{int(frequency):,}"| {node_id[target]}'
        for source, target, frequency in edges
    ]
    lines += [
        f"    linkStyle {index} stroke-width:{_stroke_width(int(frequency), max_frequency)}px"
        for index, (_, _, frequency) in enumerate(edges)
    ]

    total = dfg.transition_count
    shown_transitions = int(shown[FREQUENCY].sum()) if len(shown) else 0
    return MermaidDiagram(
        text="\n".join(lines) + "\n",
        edges_shown=len(shown),
        edges_total=len(dfg.edges),
        transition_share=shown_transitions / total if total else 0.0,
    )
