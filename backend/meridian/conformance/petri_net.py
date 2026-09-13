"""A small labelled Petri net: the structure real cases are replayed against.

02-TECH-STACK-AND-SKILLS.md §2 accepts a simplified "directed graph with required order", but the
formal places-and-transitions version is implemented instead. Why: token-based replay is defined
on Petri nets, and "missing" and "remaining" tokens only mean something when there are places for
a token to be missing from or left behind in. The simplification that remains, and is relied on by
replay, is that every transition is visible: each carries an activity label, and there are no
silent transitions.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from functools import cached_property


@dataclass(frozen=True)
class Transition:
    """One process step: firing it takes a token from each input place and puts one in each output.

    `id` is unique within a net; `label` is the activity it represents. Labels may repeat, because a
    reference process can legitimately require the same activity twice.
    """

    id: str
    label: str
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]


@dataclass(frozen=True)
class PetriNet:
    """Places, labelled transitions, and the markings a complete case starts from and must end in.

    Markings map place names to token counts. The net validates itself on construction, so replay
    never has to handle arcs to places that do not exist.
    """

    places: tuple[str, ...]
    transitions: tuple[Transition, ...]
    initial_marking: Mapping[str, int]
    final_marking: Mapping[str, int]

    def __post_init__(self) -> None:
        """Reject structurally broken nets: unknown places, duplicate names, empty markings."""
        known = set(self.places)
        if len(known) != len(self.places):
            raise ValueError("Petri net has duplicate place names")
        ids = [transition.id for transition in self.transitions]
        if len(set(ids)) != len(ids):
            raise ValueError("Petri net has duplicate transition ids")
        for transition in self.transitions:
            unknown = (set(transition.inputs) | set(transition.outputs)) - known
            if unknown:
                raise ValueError(
                    f"Transition {transition.id} uses unknown places: {sorted(unknown)}"
                )
        for name, marking in (("initial", self.initial_marking), ("final", self.final_marking)):
            unknown = set(marking) - known
            if unknown:
                raise ValueError(f"The {name} marking uses unknown places: {sorted(unknown)}")
            if any(tokens < 0 for tokens in marking.values()):
                raise ValueError(f"The {name} marking has a negative token count")
            if sum(marking.values()) == 0:
                raise ValueError(f"The {name} marking must hold at least one token")

    @cached_property
    def _by_label(self) -> dict[str, tuple[Transition, ...]]:
        """Label-to-transitions index, built once; transitions keep their order in the net."""
        index: dict[str, list[Transition]] = {}
        for transition in self.transitions:
            index.setdefault(transition.label, []).append(transition)
        return {label: tuple(found) for label, found in index.items()}

    @property
    def labels(self) -> frozenset[str]:
        """Every activity the model knows about."""
        return frozenset(self._by_label)

    def transitions_for(self, label: str) -> tuple[Transition, ...]:
        """Transitions carrying `label`, in net order; empty if the activity is not in the model."""
        return self._by_label.get(label, ())


def sequence_net(activities: Sequence[str]) -> PetriNet:
    """Build the Petri net of a strict sequence: the first activity, then the second, and so on.

    Places p0..pn chain the steps: transition t_i takes its token from p_i and puts it in p_(i+1).
    A case starts with one token in p0 and should finish with exactly one token in pn. Why this
    shape: it is the formal version of "these steps, in this order", so a skipped step shows up as
    a token missing where the next step needed it, and an out-of-order or repeated step as a token
    left behind.
    """
    if not activities:
        raise ValueError("A reference sequence needs at least one activity")
    places = tuple(f"p{index}" for index in range(len(activities) + 1))
    transitions = tuple(
        Transition(
            id=f"t{index}", label=activity, inputs=(places[index],), outputs=(places[index + 1],)
        )
        for index, activity in enumerate(activities)
    )
    return PetriNet(
        places=places,
        transitions=transitions,
        initial_marking={places[0]: 1},
        final_marking={places[-1]: 1},
    )
