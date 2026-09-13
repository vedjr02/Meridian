"""Per-case statistics and cycle-time distributions (Module A requirement 4, acceptance d).

Cycle time is reported as a distribution (percentiles), never as a mean alone: service-process
durations are right-skewed, so a few very long cases pull the mean well above what a typical
case experiences (03-UIUX-RULES.md rule 1).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from meridian.discovery.variants import VARIANT_RANK, VariantAnalysis
from meridian.ingestion import schema

START_TIME = "start_time"
END_TIME = "end_time"
CYCLE_TIME = "cycle_time_seconds"
ACTIVITY_COUNT = "activity_count"
IS_HAPPY_PATH = "is_happy_path"
CASE_STATISTICS_COLUMNS = (
    schema.CASE_ID,
    START_TIME,
    END_TIME,
    CYCLE_TIME,
    ACTIVITY_COUNT,
    VARIANT_RANK,
    IS_HAPPY_PATH,
    schema.OUTCOME,
)


@dataclass(frozen=True)
class DistributionSummary:
    """A duration distribution in seconds: size, spread and the percentiles that describe its shape.

    Percentiles use linear interpolation between order statistics (numpy's default method), stated
    so that anyone recomputing them in another tool can match the numbers exactly.
    """

    count: int
    mean: float
    minimum: float
    p50: float
    p90: float
    p99: float
    maximum: float

    def to_dict(self) -> dict[str, float | int]:
        """Return a JSON-serialisable form."""
        return {
            "count": self.count,
            "mean": self.mean,
            "min": self.minimum,
            "p50": self.p50,
            "p90": self.p90,
            "p99": self.p99,
            "max": self.maximum,
        }


def summarize_distribution(seconds: pd.Series) -> DistributionSummary:
    """Summarize a set of durations as count, mean, min, p50, p90, p99 and max.

    Why p90 and p99 alongside the median: the median describes a typical case, while the tail
    percentiles describe the cases that generate complaints and cost. A process whose p99 is ten
    times its median has a different problem from one where every case is uniformly slow.
    """
    values = pd.to_numeric(seconds, errors="raise").dropna().to_numpy(dtype=float)
    if values.size == 0:
        raise ValueError("Cannot summarize an empty distribution")
    p50, p90, p99 = np.percentile(values, [50, 90, 99])
    return DistributionSummary(
        count=int(values.size),
        mean=float(values.mean()),
        minimum=float(values.min()),
        p50=float(p50),
        p90=float(p90),
        p99=float(p99),
        maximum=float(values.max()),
    )


def case_statistics(event_log: pd.DataFrame, variants: VariantAnalysis) -> pd.DataFrame:
    """Compute per-case cycle time, activity count, variant and happy-path flag.

    Cycle time is the span from a case's first to its last recorded event. It therefore depends on
    which lifecycle transitions ingestion kept (08-OPEN-QUESTIONS.md), and for cases with no
    terminal outcome it is a lower bound, because those cases were still running when the log was
    extracted.

    Why "happy path" means following the most frequent variant exactly: 01-REQUIREMENTS.md defines
    it that way, and it needs no assumption about which process was intended; Module B introduces
    reference models for that.
    """
    by_case = event_log.groupby(schema.CASE_ID, sort=True)
    stats = by_case.agg(
        **{
            START_TIME: (schema.TIMESTAMP, "min"),
            END_TIME: (schema.TIMESTAMP, "max"),
            ACTIVITY_COUNT: (schema.ACTIVITY, "size"),
        }
    )
    stats[CYCLE_TIME] = (stats[END_TIME] - stats[START_TIME]).dt.total_seconds()
    stats[VARIANT_RANK] = variants.case_variants.reindex(stats.index).astype("int64")
    stats[IS_HAPPY_PATH] = stats[VARIANT_RANK] == 1
    if schema.OUTCOME in event_log.columns:
        stats[schema.OUTCOME] = by_case[schema.OUTCOME].first()
    else:
        stats[schema.OUTCOME] = pd.NA
    return stats.reset_index().loc[:, list(CASE_STATISTICS_COLUMNS)]
