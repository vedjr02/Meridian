"""Lifecycle policy: which lifecycle transition becomes the one event per activity occurrence.

The normalized schema has a single timestamp per event, but BPI 2017 records work items with
schedule / start / suspend / resume / complete / ate_abort / withdraw transitions. A policy says
which transition represents an occurrence. Decided by Ved on 2026-09-13 (08-OPEN-QUESTIONS.md):
`START_ELSE_COMPLETE` is the default, because complete-only undercounts human work items by ~99%
(most `W_` items end in `ate_abort`, not `complete`).
"""

from __future__ import annotations

from enum import StrEnum


class LifecyclePolicy(StrEnum):
    """Rule for choosing each activity occurrence's single lifecycle event."""

    START_ELSE_COMPLETE = "start_else_complete"
    COMPLETE = "complete"
    ALL = "all"

    @property
    def description(self) -> str:
        """Short human-readable name for reports and the UI."""
        return {
            LifecyclePolicy.START_ELSE_COMPLETE: "start where recorded, otherwise complete",
            LifecyclePolicy.COMPLETE: "complete only",
            LifecyclePolicy.ALL: "every transition",
        }[self]

    @property
    def caveat(self) -> str:
        """What a reader must know about durations and counts produced under this policy.

        Why each policy has its own wording: each one distorts time differently, and a generic
        "lifecycle filter applies" note would not tell a reader which numbers to be careful with.
        """
        return {
            LifecyclePolicy.START_ELSE_COMPLETE: (
                "Activities that record start events are represented by when work started; all "
                "others by when they completed. A wait into a started activity therefore ends when "
                "work begins, and a case ending with a started activity excludes that activity's "
                "own processing time from its cycle time."
            ),
            LifecyclePolicy.COMPLETE: (
                "Only completion events are kept, so work items that start but end without "
                "completing (aborted or withdrawn) are missing, which undercounts human work."
            ),
            LifecyclePolicy.ALL: (
                "Every lifecycle transition is a separate event, so one work item can appear "
                "several times in a path and waits include time between its own transitions."
            ),
        }[self]
