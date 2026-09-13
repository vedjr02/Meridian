"""Token-based replay: play a real case through the reference Petri net and count what went wrong.

02-TECH-STACK-AND-SKILLS.md §2, implemented by hand. For each event, the transition labelled with
its activity fires:
- if an input place holds no token, the case skipped a step the model requires: a token is
  inserted so replay can continue, and counted as **missing**;
- tokens still in places after the case ends mark steps the model expected to follow but the case
  never performed: **remaining**;
- an event whose activity the model does not contain is an extra step. It is replayed as if it were
  a transition with its own empty input place and an output place nothing reads from, so it costs
  one missing and one remaining token.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

from meridian.conformance.petri_net import PetriNet, Transition


@dataclass(frozen=True)
class ReplayResult:
    """Token counts from replaying one case, and the fitness derived from them.

    Attributes:
        produced: Tokens created, including the initial marking (p).
        consumed: Tokens used, including those taken by the final marking (c).
        missing: Tokens that had to be inserted because a required step was skipped (m).
        remaining: Tokens left over when the case ended (r).
        unknown_activities: Events whose activity is not in the reference model.

    Conservation holds for every case: remaining - missing == produced - consumed.
    """

    produced: int
    consumed: int
    missing: int
    remaining: int
    unknown_activities: int

    @property
    def fitness(self) -> float:
        """Token-replay fitness: 0.5 * (1 - m/c) + 0.5 * (1 - r/p).

        Why this formula (Rozinat and van der Aalst, "Conformance checking of processes based on
        monitoring real behavior", Information Systems 33(1), 2008) rather than the single ratio
        1 - (m + r) / (expected + actual) suggested in 02-TECH-STACK: it scores the two kinds of
        deviation separately, missing tokens against what the case consumed and remaining tokens
        against what it produced, so a large count of one cannot dilute the other. It is also the
        standard token-replay fitness, so the numbers are comparable with other tools.

        It is 1 exactly when the model explains the case with nothing missing or left over, and
        never below 0: every missing token is later consumed (m <= c) and every remaining token
        was produced (r <= p). c and p are never 0 because the markings always count.
        """
        return 0.5 * (1 - self.missing / self.consumed) + 0.5 * (1 - self.remaining / self.produced)

    @property
    def fits(self) -> bool:
        """Whether the case followed the reference exactly: no missing and no remaining tokens."""
        return self.missing == 0 and self.remaining == 0


def _missing_if_fired(transition: Transition, marking: Counter[str]) -> int:
    """Tokens that would have to be inserted for `transition` to fire in `marking`."""
    needed = Counter(transition.inputs)
    return sum(max(0, count - marking[place]) for place, count in needed.items())


def _choose_transition(candidates: tuple[Transition, ...], marking: Counter[str]) -> Transition:
    """Pick which transition fires when an activity labels several (a step the model repeats).

    The one needing the fewest inserted tokens wins, and ties go to the earliest in the net. Why:
    it explains the event with the least invented evidence, and a fixed tie-break keeps replay
    deterministic. It is a local choice and can occasionally make a later step look worse; that is
    the accepted trade-off of token replay compared with full alignment-based conformance.
    """
    return min(candidates, key=lambda transition: _missing_if_fired(transition, marking))


def replay_trace(net: PetriNet, trace: Sequence[str]) -> ReplayResult:
    """Replay one case's activity sequence through `net` and return its token counts.

    Why tokens are inserted rather than replay stopping at the first deviation: the rest of the
    case still carries information. Stopping would score a case that skipped its second step the
    same as one that did nothing right at all.
    """
    marking: Counter[str] = Counter(net.initial_marking)
    produced = sum(net.initial_marking.values())
    consumed = missing = unknown = 0

    for activity in trace:
        candidates = net.transitions_for(activity)
        if not candidates:
            unknown += 1
            missing += 1
            consumed += 1
            produced += 1
            continue
        transition = _choose_transition(candidates, marking)
        for place in transition.inputs:
            if marking[place] == 0:
                missing += 1
                marking[place] += 1
            marking[place] -= 1
            consumed += 1
        for place in transition.outputs:
            marking[place] += 1
            produced += 1

    for place, required in net.final_marking.items():
        missing += max(0, required - marking[place])
        marking[place] = max(0, marking[place] - required)
        consumed += required

    remaining = sum(marking.values()) + unknown
    return ReplayResult(
        produced=produced,
        consumed=consumed,
        missing=missing,
        remaining=remaining,
        unknown_activities=unknown,
    )
