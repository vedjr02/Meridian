"""Layered left-to-right layout for the process map, computed without a layout library.

Why hand-written: the graph libraries in the tech stack (react-force-graph, d3-force) produce
force-directed layouts, which scatter a process map's natural left-to-right flow, and layered
layout libraries (dagre, elkjs) are not in the stack. This implements the first two steps of the
classic layered (Sugiyama) approach: assign each activity a stage, then reorder activities within
each stage to reduce edge crossings. It is deterministic, so the map looks the same on every run.
"""

from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Iterable
from dataclasses import dataclass

# Spacing in drawing units, sized for compact 164 x 42 activity boxes: tight enough that the
# BPI 2017 model (7 stages, up to 8 activities per stage) stays legible when fitted to a laptop
# screen, loose enough that arrows between neighbouring stages remain distinguishable.
LAYER_SPACING = 210.0
ROW_SPACING = 64.0
ORDERING_SWEEPS = 4


@dataclass(frozen=True)
class NodePosition:
    """Where an activity sits: its stage (layer), its rank within the stage, and coordinates."""

    activity: str
    layer: int
    order: int
    x: float
    y: float


def layered_layout(
    activities: Iterable[str],
    edges: Iterable[tuple[str, str]],
    start_activities: Iterable[str],
) -> dict[str, NodePosition]:
    """Assign every activity a layer and an order within it, and derive x/y coordinates.

    Layers are breadth-first distances from the start activities, so an activity sits one stage
    after the earliest activity that can lead to it. Why shortest distance: loops and rework edges
    point backwards and must not push activities further right, which longest-path layering
    would do once cycles are broken arbitrarily. Activities unreachable from any start go in one
    extra layer at the end, so they stay visible instead of overlapping stage 0.

    Order within a layer uses barycenter sweeps: each activity moves toward the average position
    of its neighbours in the adjacent layer, alternating left-to-right and right-to-left passes.
    Ties keep the previous order and then the name, so the result never depends on input order.
    Self-loops are ignored for placement.
    """
    nodes = sorted(set(activities))
    known = set(nodes)
    successors: dict[str, set[str]] = {node: set() for node in nodes}
    predecessors: dict[str, set[str]] = {node: set() for node in nodes}
    for source, target in edges:
        if source != target and source in known and target in known:
            successors[source].add(target)
            predecessors[target].add(source)

    layer_of = _breadth_first_layers(nodes, successors, start_activities)
    layers: dict[int, list[str]] = defaultdict(list)
    for node in nodes:
        layers[layer_of[node]].append(node)
    _reduce_crossings(layers, layer_of, successors, predecessors)

    positions = {}
    for layer, members in layers.items():
        centre = (len(members) - 1) / 2
        for order, node in enumerate(members):
            positions[node] = NodePosition(
                activity=node,
                layer=layer,
                order=order,
                x=layer * LAYER_SPACING,
                y=(order - centre) * ROW_SPACING,
            )
    return positions


def _breadth_first_layers(
    nodes: list[str], successors: dict[str, set[str]], start_activities: Iterable[str]
) -> dict[str, int]:
    """Layer each node by its shortest distance from any start activity."""
    starts = sorted(set(start_activities) & set(nodes))
    layer_of = {start: 0 for start in starts}
    queue = deque(starts)
    while queue:
        node = queue.popleft()
        for successor in sorted(successors[node]):
            if successor not in layer_of:
                layer_of[successor] = layer_of[node] + 1
                queue.append(successor)
    unreached_layer = max(layer_of.values(), default=-1) + 1
    for node in nodes:
        layer_of.setdefault(node, unreached_layer)
    return layer_of


def _reduce_crossings(
    layers: dict[int, list[str]],
    layer_of: dict[str, int],
    successors: dict[str, set[str]],
    predecessors: dict[str, set[str]],
) -> None:
    """Reorder each layer in place with alternating barycenter sweeps."""
    position = {node: order for members in layers.values() for order, node in enumerate(members)}
    for sweep in range(ORDERING_SWEEPS):
        forward = sweep % 2 == 0
        for layer in sorted(layers, reverse=not forward):
            reference = layer - 1 if forward else layer + 1

            def barycenter(node: str, reference: int = reference) -> float:
                """Average position of the node's neighbours in the reference layer."""
                neighbours = [
                    other
                    for other in predecessors[node] | successors[node]
                    if layer_of[other] == reference
                ]
                if not neighbours:
                    return float(position[node])
                return sum(position[other] for other in neighbours) / len(neighbours)

            layers[layer].sort(key=lambda node: (barycenter(node), position[node], node))
            for order, node in enumerate(layers[layer]):
                position[node] = order


def count_crossings(positions: dict[str, NodePosition], edges: Iterable[tuple[str, str]]) -> int:
    """Count pairs of edges between adjacent layers that cross each other.

    Used by tests to show the ordering step does its job; only edges spanning exactly one layer
    to the right are compared, which is where crossings are unambiguous.
    """
    spans = [
        (positions[s].layer, positions[s].order, positions[t].order)
        for s, t in edges
        if s in positions and t in positions and positions[t].layer == positions[s].layer + 1
    ]
    crossings = 0
    for i, (layer_a, from_a, to_a) in enumerate(spans):
        for layer_b, from_b, to_b in spans[i + 1 :]:
            if layer_a == layer_b and (from_a - from_b) * (to_a - to_b) < 0:
                crossings += 1
    return crossings
