"""Tests for the API skeleton's health-check endpoint."""

from fastapi.testclient import TestClient

from meridian import __version__
from meridian.api.main import create_app


def test_health_reports_ok_and_version() -> None:
    """The health endpoint is the first thing the frontend and any deploy check rely on.

    Asserting the exact payload (not just a 200) catches a server answering from a stale build.
    """
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": __version__}
