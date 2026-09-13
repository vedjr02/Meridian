"""Tests for the process discovery API, served from outputs of a real discovery run.

The synthetic log (conftest `discovery_settings`) has three cases: two follow Submit, Review,
Approve over 2 h, one follows Submit, Reject over 1 h.
"""

import os

import pytest
from fastapi.testclient import TestClient

from meridian.api.discovery import settings_dependency
from meridian.api.main import create_app
from meridian.discovery.pipeline import run_discovery


def _client_for(settings) -> TestClient:
    """An app whose endpoints read the given settings' processed data."""
    app = create_app()
    app.dependency_overrides[settings_dependency] = lambda: settings
    return TestClient(app)


@pytest.fixture
def client(discovery_settings) -> TestClient:
    """Client over a completed discovery run on the synthetic log."""
    run_discovery(discovery_settings, load_database=False)
    return _client_for(discovery_settings)


def test_overview_headline_numbers(client) -> None:
    """Scale, coverage and distributions match the synthetic log exactly."""
    body = client.get("/api/discovery/overview").json()

    assert (body["case_count"], body["event_count"], body["activity_count"]) == (3, 8, 4)
    assert (body["variant_count"], body["variants_to_cover"]) == (2, 2)
    assert body["top_variant_share"] == pytest.approx(2 / 3)
    assert body["lifecycle"]["policy"] == "start_else_complete"
    assert body["lifecycle"]["caveat"].startswith("Lifecycle rule: start where recorded")
    cycle = body["cycle_time_seconds"]
    assert cycle["all_cases"]["p50"] == 7200.0
    assert cycle["most_common_variant"]["count"] == 2
    assert cycle["other_variants"]["count"] == 1


def test_process_map_has_positions_kinds_and_timing(client) -> None:
    """Every node is placed, every edge joins known nodes and carries its DFG timing."""
    body = client.get("/api/discovery/process-map").json()

    nodes = {node["id"]: node for node in body["nodes"]}
    assert set(nodes) == {"Submit", "Review", "Approve", "Reject"}
    assert (nodes["Submit"]["layer"], nodes["Submit"]["start_count"]) == (0, 3)
    assert nodes["Approve"]["layer"] == 2
    for edge in body["edges"]:
        assert {edge["source"], edge["target"]} <= set(nodes)
        assert edge["kind"] and edge["median_duration_seconds"] is not None
    review_to_approve = next(e for e in body["edges"] if e["source"] == "Review")
    assert review_to_approve["median_duration_seconds"] == 3600.0


def test_variants_with_sequences_outcomes_and_limit(client) -> None:
    """Variants carry their activity sequence and outcome counts; `limit` is validated."""
    body = client.get("/api/discovery/variants", params={"limit": 1}).json()

    assert body["variant_count"] == 2
    assert body["variants"] == [
        {
            "rank": 1,
            "activities": ["Submit", "Review", "Approve"],
            "case_count": 2,
            "case_share": pytest.approx(2 / 3),
            "cumulative_share": pytest.approx(2 / 3),
            "outcomes": {"approved": 2},
        }
    ]
    assert client.get("/api/discovery/variants", params={"limit": 0}).status_code == 422


def test_histogram_accounts_for_every_case(client) -> None:
    """Bins plus overflow hold every case; percentile markers are reported in days."""
    body = client.get("/api/discovery/cycle-time/histogram").json()

    total = sum(b["all_cases"] for b in body["bins"]) + body["overflow"]["all_cases"]
    assert total == body["case_count"] == 3
    assert body["unit"] == "days"
    assert body["percentiles"]["p50"] == pytest.approx(2 / 24)


@pytest.mark.parametrize(
    "path",
    [
        "/api/discovery/overview",
        "/api/discovery/process-map",
        "/api/discovery/variants",
        "/api/discovery/cycle-time/histogram",
    ],
)
def test_missing_outputs_return_actionable_404(discovery_settings, path: str) -> None:
    """Before discovery has run, each endpoint says so and names the command to run."""
    response = _client_for(discovery_settings).get(path)

    assert response.status_code == 404
    detail = response.json()["detail"]
    assert detail["code"] == "discovery_outputs_missing"
    assert "python -m meridian.discovery" in detail["message"]
    assert detail["missing"]


def test_rewritten_outputs_are_served_fresh(client, discovery_settings) -> None:
    """A rerun of discovery rewrites the files; the API must not keep serving the old numbers."""
    assert client.get("/api/discovery/overview").json()["variant_count"] == 2

    path = discovery_settings.variants_csv
    lines = path.read_text().splitlines()
    path.write_text("\n".join(lines[:2]) + "\n")
    stat = path.stat()
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000))

    assert client.get("/api/discovery/overview").json()["variant_count"] == 1
