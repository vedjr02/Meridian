"""Read-only API over Module A's outputs, for the frontend's process discovery view.

Endpoints serve what `python -m meridian.discovery` already computed. The only per-request work is
reshaping (layout, histogram bins, outcome grouping), so the page shows exactly the numbers in the
written summary rather than a second, possibly different, computation.
"""

from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query

from meridian.config import Settings, get_settings
from meridian.discovery.cycle_time import CYCLE_TIME, IS_HAPPY_PATH, summarize_distribution
from meridian.discovery.layout import layered_layout
from meridian.discovery.pipeline import COVERAGE_SHARE, recorded_lifecycle_policy
from meridian.discovery.summary import NO_OUTCOME, lifecycle_caveat, lifecycle_label
from meridian.discovery.variants import (
    CASE_COUNT,
    CASE_SHARE,
    CUMULATIVE_SHARE,
    SEPARATOR,
    VARIANT,
    VARIANT_RANK,
    variants_needed,
)
from meridian.ingestion import schema

router = APIRouter(prefix="/api/discovery", tags=["process discovery"])

MAX_VARIANTS = 200
HISTOGRAM_MAX_BINS = 30
SECONDS_PER_DAY = 86_400


def settings_dependency() -> Settings:
    """Resolve settings per request; tests override this to point at temporary data."""
    return get_settings()


SettingsDep = Annotated[Settings, Depends(settings_dependency)]


def _require(*paths: Path) -> None:
    """Raise a structured 404 naming the missing outputs and the command that produces them.

    Why 404 and not 500: missing outputs are an expected state (discovery has not run yet), which
    the frontend shows as a designed empty state with instructions, not as a failure.
    """
    missing = [path.name for path in paths if not path.exists()]
    if missing:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "discovery_outputs_missing",
                "message": (
                    "Process discovery has not been run yet. "
                    "Run `python -m meridian.discovery` to produce these outputs."
                ),
                "missing": missing,
            },
        )


@lru_cache(maxsize=16)
def _read_csv(path: str, modified_ns: int) -> pd.DataFrame:
    """Read a CSV once per file version. Callers must treat the result as read-only.

    `modified_ns` is part of the cache key so a rerun of discovery, which rewrites the file, is
    picked up immediately instead of serving stale numbers. Only empty cells count as missing, as
    in ingestion, so labels like "NA" survive.
    """
    return pd.read_csv(path, keep_default_na=False, na_values=[""])


@lru_cache(maxsize=4)
def _read_json(path: str, modified_ns: int) -> dict[str, Any]:
    """Read a JSON file once per file version. Callers must treat the result as read-only."""
    return json.loads(Path(path).read_text())


def _csv(path: Path) -> pd.DataFrame:
    """Cached CSV read keyed on the file's current modification time."""
    return _read_csv(str(path), path.stat().st_mtime_ns)


def _json(path: Path) -> dict[str, Any]:
    """Cached JSON read keyed on the file's current modification time."""
    return _read_json(str(path), path.stat().st_mtime_ns)


@router.get("/overview")
def overview(settings: SettingsDep) -> dict[str, Any]:
    """Headline numbers: scale, variant coverage, and cycle time as distributions (in seconds)."""
    _require(settings.heuristic_net_json, settings.variants_csv, settings.case_statistics_csv)
    model = _json(settings.heuristic_net_json)
    variants = _csv(settings.variants_csv)
    stats = _csv(settings.case_statistics_csv)
    policy = recorded_lifecycle_policy(settings)
    happy = stats[stats[IS_HAPPY_PATH]]
    others = stats[~stats[IS_HAPPY_PATH]]
    return {
        "dataset": settings.dataset.name,
        "lifecycle": {
            "policy": policy.value if policy else None,
            "description": lifecycle_label(policy),
            "caveat": lifecycle_caveat(policy),
        },
        "case_count": len(stats),
        "event_count": int(sum(model["activities"].values())),
        "activity_count": len(model["activities"]),
        "variant_count": len(variants),
        "coverage_share": COVERAGE_SHARE,
        "variants_to_cover": variants_needed(variants[CASE_COUNT].tolist(), COVERAGE_SHARE),
        "top_variant_share": float(variants[CASE_SHARE].iloc[0]) if len(variants) else 0.0,
        "open_case_count": int(stats[schema.OUTCOME].isna().sum()),
        "cycle_time_seconds": {
            "all_cases": summarize_distribution(stats[CYCLE_TIME]).to_dict(),
            "most_common_variant": summarize_distribution(happy[CYCLE_TIME]).to_dict(),
            "other_variants": (
                summarize_distribution(others[CYCLE_TIME]).to_dict() if len(others) else None
            ),
        },
    }


@router.get("/process-map")
def process_map(settings: SettingsDep) -> dict[str, Any]:
    """The mined model with layered coordinates and DFG timing per edge, ready to draw.

    Why the layout is computed here and not in the browser: it is deterministic, tested Python,
    so every client draws the identical map.
    """
    _require(settings.heuristic_net_json, settings.dfg_edges_csv)
    model = _json(settings.heuristic_net_json)
    timing = {
        (row.source, row.target): (int(row.case_frequency), float(row.median_duration_seconds))
        for row in _csv(settings.dfg_edges_csv).itertuples(index=False)
    }
    positions = layered_layout(
        model["activities"],
        [(edge["source"], edge["target"]) for edge in model["edges"]],
        model["start_activities"],
    )
    nodes = [
        {
            "id": activity,
            "count": int(count),
            "start_count": int(model["start_activities"].get(activity, 0)),
            "end_count": int(model["end_activities"].get(activity, 0)),
            "layer": positions[activity].layer,
            "order": positions[activity].order,
            "x": positions[activity].x,
            "y": positions[activity].y,
        }
        for activity, count in sorted(model["activities"].items())
    ]
    edges = []
    for edge in model["edges"]:
        case_frequency, median = timing.get((edge["source"], edge["target"]), (None, None))
        edges.append(edge | {"case_frequency": case_frequency, "median_duration_seconds": median})
    return {
        "threshold": model["threshold"],
        "case_count": model["case_count"],
        "nodes": nodes,
        "edges": edges,
    }


@router.get("/variants")
def variants(
    settings: SettingsDep,
    limit: Annotated[int, Query(ge=1, le=MAX_VARIANTS)] = 25,
) -> dict[str, Any]:
    """The most frequent variants with activity sequences and each variant's outcome counts.

    Sequences are split from the saved display text, so an activity name containing the " > "
    separator would be split wrongly; no BPI 2017 activity contains it.
    """
    _require(settings.variants_csv, settings.case_statistics_csv)
    table = _csv(settings.variants_csv)
    stats = _csv(settings.case_statistics_csv)

    outcome_labels = (
        stats[schema.OUTCOME].astype("object").where(stats[schema.OUTCOME].notna(), NO_OUTCOME)
    )
    outcomes: dict[int, dict[str, int]] = {}
    for (rank, label), count in (
        pd.DataFrame({VARIANT_RANK: stats[VARIANT_RANK], schema.OUTCOME: outcome_labels})
        .groupby([VARIANT_RANK, schema.OUTCOME])
        .size()
        .items()
    ):
        outcomes.setdefault(int(rank), {})[str(label)] = int(count)

    rows = [
        {
            "rank": int(getattr(row, VARIANT_RANK)),
            "activities": str(getattr(row, VARIANT)).split(SEPARATOR),
            "case_count": int(getattr(row, CASE_COUNT)),
            "case_share": float(getattr(row, CASE_SHARE)),
            "cumulative_share": float(getattr(row, CUMULATIVE_SHARE)),
            "outcomes": outcomes.get(int(getattr(row, VARIANT_RANK)), {}),
        }
        for row in table.head(limit).itertuples(index=False)
    ]
    return {"case_count": len(stats), "variant_count": len(table), "variants": rows}


@router.get("/cycle-time/histogram")
def cycle_time_histogram(settings: SettingsDep) -> dict[str, Any]:
    """Cycle-time histogram in days with p50/p90/p99 markers, for all cases and the top variant.

    Fixed binning rule, so the chart is reproducible: bins run from 0 to p99 rounded up to a whole
    day, using at most 30 equal bins of a whole number of days. Cases beyond the last bin go in an
    explicit overflow bin rather than stretching the axis, so the long tail is reported, not hidden
    and not allowed to flatten the rest of the distribution.
    """
    _require(settings.case_statistics_csv)
    stats = _csv(settings.case_statistics_csv)
    days = stats[CYCLE_TIME].to_numpy(dtype=float) / SECONDS_PER_DAY
    happy = stats[IS_HAPPY_PATH].to_numpy(dtype=bool)
    summary = summarize_distribution(stats[CYCLE_TIME])

    upper = max(1, math.ceil(summary.p99 / SECONDS_PER_DAY))
    width = max(1, math.ceil(upper / HISTOGRAM_MAX_BINS))
    bin_count = math.ceil(upper / width)
    bin_index = np.floor(days / width).astype(int)

    bins = [
        {
            "start": float(i * width),
            "end": float((i + 1) * width),
            "all_cases": int((bin_index == i).sum()),
            "most_common_variant": int(((bin_index == i) & happy).sum()),
        }
        for i in range(bin_count)
    ]
    overflow = bin_index >= bin_count
    return {
        "unit": "days",
        "case_count": len(stats),
        "bin_width": float(width),
        "bins": bins,
        "overflow": {
            "start": float(bin_count * width),
            "all_cases": int(overflow.sum()),
            "most_common_variant": int((overflow & happy).sum()),
        },
        "percentiles": {
            "p50": summary.p50 / SECONDS_PER_DAY,
            "p90": summary.p90 / SECONDS_PER_DAY,
            "p99": summary.p99 / SECONDS_PER_DAY,
        },
    }
